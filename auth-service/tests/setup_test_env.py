"""Setup script for test environment."""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from src.models import Base
from src.config import settings


async def setup_test_database():
    """Create test database and tables."""
    print("Setting up test database...")
    
    # Use test database URL
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/auth_test"
    )
    
    # Create engine
    engine = create_async_engine(test_db_url, echo=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("Test database setup complete!")


async def create_test_data():
    """Create initial test data."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from src.models.user import User, UserStatus
    from src.models.rbac import Role, Permission, RolePermission
    from src.security.passwords import PasswordService
    
    print("Creating test data...")
    
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/auth_test"
    )
    
    engine = create_async_engine(test_db_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession)
    
    async with SessionLocal() as session:
        password_service = PasswordService()
        
        # Create roles
        admin_role = Role(
            name="admin",
            display_name="Administrator",
            description="Full system access",
            priority=1000
        )
        
        user_role = Role(
            name="user",
            display_name="User",
            description="Standard user access",
            priority=100
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
                name="user_read",
                display_name="Read Users",
                resource_type="user",
                allowed_actions=["read"]
            ),
            Permission(
                name="user_write",
                display_name="Write Users",
                resource_type="user",
                allowed_actions=["create", "update", "delete"]
            )
        ]
        
        session.add_all([admin_role, user_role] + permissions)
        await session.flush()
        
        # Assign permissions to roles
        for permission in permissions:
            if permission.name == "admin_access" or "user" in permission.name:
                session.add(RolePermission(
                    role_id=admin_role.id,
                    permission_id=permission.id
                ))
        
        session.add(RolePermission(
            role_id=user_role.id,
            permission_id=permissions[1].id  # user_read only
        ))
        
        # Create test users
        test_admin = User(
            email="test.admin@example.com",
            username="testadmin",
            full_name="Test Admin",
            password_hash=password_service.hash_password("Admin123!@#"),
            status=UserStatus.ACTIVE,
            email_verified=True,
            is_system_user=True
        )
        
        test_user = User(
            email="test.user@example.com",
            username="testuser",
            full_name="Test User",
            password_hash=password_service.hash_password("User123!@#"),
            status=UserStatus.ACTIVE,
            email_verified=True
        )
        
        session.add_all([test_admin, test_user])
        await session.commit()
        
    await engine.dispose()
    print("Test data created successfully!")


async def main():
    """Run setup tasks."""
    try:
        await setup_test_database()
        await create_test_data()
        print("\nTest environment setup complete!")
        print("\nTest users created:")
        print("  Admin: test.admin@example.com / Admin123!@#")
        print("  User:  test.user@example.com / User123!@#")
    except Exception as e:
        print(f"Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())