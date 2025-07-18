"""Pytest configuration and fixtures for auth service tests."""

import asyncio
import os
from typing import AsyncGenerator, Generator
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import redis.asyncio as redis

from src.models import Base
from src.models.user import User, UserStatus, UserRole
from src.models.rbac import Role, Permission, RolePermission
from src.models.mfa import MFASetup, MFABackupCode
from src.models.session import UserSession
from src.database import get_db, get_redis
from src.security.passwords import PasswordService
from src.security.tokens import TokenService
from src.config import settings
from main_complete import app


# Test database URL
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/auth_test"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    TestSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Create test Redis client."""
    client = await redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    
    # Clear test data
    await client.flushdb()
    
    yield client
    
    await client.close()


@pytest.fixture(scope="function")
def test_client(db: AsyncSession, redis_client: redis.Redis) -> TestClient:
    """Create test client with overridden dependencies."""
    async def override_get_db():
        yield db
    
    async def override_get_redis():
        return redis_client
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def password_service() -> PasswordService:
    """Create password service instance."""
    return PasswordService()


@pytest_asyncio.fixture
async def token_service() -> TokenService:
    """Create token service instance."""
    return TokenService()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, password_service: PasswordService) -> User:
    """Create test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        password_hash=password_service.hash_password("Test123!@#"),
        status=UserStatus.ACTIVE,
        email_verified=True,
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, password_service: PasswordService) -> User:
    """Create admin user with roles."""
    # Create admin role
    admin_role = Role(
        name="admin",
        display_name="Administrator",
        description="Full system access",
        priority=1000
    )
    
    # Create permissions
    permissions = [
        Permission(
            name="admin_access",
            display_name="Admin Access",
            resource_type="admin",
            allowed_actions=["*"]
        ),
        Permission(
            name="user_manage",
            display_name="Manage Users",
            resource_type="user",
            allowed_actions=["create", "read", "update", "delete"]
        ),
        Permission(
            name="role_manage",
            display_name="Manage Roles",
            resource_type="role",
            allowed_actions=["create", "read", "update", "delete"]
        )
    ]
    
    db.add(admin_role)
    db.add_all(permissions)
    await db.flush()
    
    # Assign permissions to role
    for permission in permissions:
        role_permission = RolePermission(
            role_id=admin_role.id,
            permission_id=permission.id
        )
        db.add(role_permission)
    
    # Create admin user
    admin = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        password_hash=password_service.hash_password("Admin123!@#"),
        status=UserStatus.ACTIVE,
        email_verified=True,
        is_system_user=True
    )
    
    db.add(admin)
    await db.flush()
    
    # Assign role to user
    user_role = UserRole(
        user_id=admin.id,
        role_id=admin_role.id,
        assigned_by=admin.id
    )
    db.add(user_role)
    
    await db.commit()
    await db.refresh(admin)
    
    return admin


@pytest_asyncio.fixture
async def user_with_mfa(db: AsyncSession, test_user: User) -> User:
    """Create user with MFA enabled."""
    import pyotp
    
    # Enable MFA
    test_user.mfa_enabled = True
    
    # Create TOTP secret
    totp_secret = MFASecret(
        user_id=test_user.id,
        method="TOTP",
        secret=pyotp.random_base32(),
        is_active=True
    )
    
    # Create backup codes
    backup_codes = []
    for i in range(10):
        code = MFABackupCode(
            user_id=test_user.id,
            code=f"BACKUP{i:04d}",
            is_used=False
        )
        backup_codes.append(code)
    
    db.add(totp_secret)
    db.add_all(backup_codes)
    await db.commit()
    await db.refresh(test_user)
    
    return test_user


@pytest_asyncio.fixture
async def auth_headers(test_user: User, token_service: TokenService) -> dict:
    """Create authorization headers for test user."""
    token = token_service.create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_user: User, token_service: TokenService) -> dict:
    """Create authorization headers for admin user."""
    token = token_service.create_access_token(str(admin_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def active_session(
    db: AsyncSession,
    test_user: User,
    token_service: TokenService
) -> UserSession:
    """Create active user session."""
    session = UserSession(
        user_id=test_user.id,
        session_token=token_service.create_access_token(str(test_user.id)),
        refresh_token=token_service.create_refresh_token(str(test_user.id)),
        expires_at=datetime.utcnow() + timedelta(days=1),
        ip_address="127.0.0.1",
        user_agent="TestClient/1.0",
        device_fingerprint="test-device-123",
        status="active"
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return session


@pytest.fixture
def oauth_providers():
    """OAuth provider configurations for testing."""
    return {
        "google": {
            "client_id": "test-google-client-id",
            "client_secret": "test-google-client-secret",
            "redirect_uri": "http://localhost:8000/auth/oauth/google/callback"
        },
        "github": {
            "client_id": "test-github-client-id",
            "client_secret": "test-github-client-secret",
            "redirect_uri": "http://localhost:8000/auth/oauth/github/callback"
        },
        "microsoft": {
            "client_id": "test-microsoft-client-id",
            "client_secret": "test-microsoft-client-secret",
            "redirect_uri": "http://localhost:8000/auth/oauth/microsoft/callback"
        }
    }


@pytest.fixture
def saml_providers():
    """SAML provider configurations for testing."""
    return {
        "okta": {
            "entity_id": "http://localhost:8000",
            "sso_url": "https://test.okta.com/sso/saml",
            "x509_cert": "-----BEGIN CERTIFICATE-----\nMIITest...\n-----END CERTIFICATE-----"
        },
        "azure": {
            "entity_id": "http://localhost:8000",
            "sso_url": "https://login.microsoftonline.com/test/saml2",
            "x509_cert": "-----BEGIN CERTIFICATE-----\nMIITest...\n-----END CERTIFICATE-----"
        }
    }


@pytest.fixture
def mock_email_service(monkeypatch):
    """Mock email service for testing."""
    sent_emails = []
    
    async def mock_send_email(to: str, subject: str, body: str, html: str = None):
        sent_emails.append({
            "to": to,
            "subject": subject,
            "body": body,
            "html": html
        })
        return True
    
    monkeypatch.setattr("src.services.email.EmailService.send_email", mock_send_email)
    return sent_emails


@pytest.fixture
def mock_sms_service(monkeypatch):
    """Mock SMS service for testing."""
    sent_messages = []
    
    async def mock_send_sms(phone: str, message: str):
        sent_messages.append({
            "phone": phone,
            "message": message
        })
        return True
    
    monkeypatch.setattr("src.services.sms.SMSService.send_sms", mock_send_sms)
    return sent_messages