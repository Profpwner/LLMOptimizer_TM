"""Test configuration and fixtures for database tests."""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

from shared.database.manager import db_manager
from shared.database.config import DatabaseConfig
from database.schemas.postgresql.models import Organization, User, Content
from database.schemas.mongodb.models import ContentDocument


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_setup():
    """Set up test databases."""
    # Initialize all database connections
    await db_manager.initialize()
    
    # Create test schema in PostgreSQL
    from database.schemas.postgresql.base import Base
    async with db_manager.postgresql._async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Cleanup
    await db_manager.close()


@pytest_asyncio.fixture
async def test_tenant(db_setup) -> AsyncGenerator[str, None]:
    """Create a test tenant for each test."""
    tenant_id = str(uuid4())
    
    # Create test organization
    org_data = {
        "name": f"Test Org {tenant_id[:8]}",
        "slug": f"test-org-{tenant_id[:8]}",
        "plan_type": "professional",
        "max_users": 10,
        "max_content_items": 100,
        "is_active": True
    }
    
    await db_manager.create_tenant(tenant_id, org_data)
    
    yield tenant_id
    
    # Cleanup
    await db_manager.delete_tenant(tenant_id)


@pytest_asyncio.fixture
async def test_user(test_tenant: str) -> AsyncGenerator[User, None]:
    """Create a test user."""
    from werkzeug.security import generate_password_hash
    
    user = User(
        id=str(uuid4()),
        email=f"test_{uuid4().hex[:8]}@example.com",
        username=f"testuser_{uuid4().hex[:8]}",
        full_name="Test User",
        password_hash=generate_password_hash("Test@1234"),
        is_email_verified=True,
        is_active=True
    )
    
    created_user = await db_manager.postgresql.create(user)
    
    # Link to organization
    async with db_manager.postgresql.get_raw_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_organizations (user_id, organization_id, role, is_primary)
            VALUES ($1, $2, $3, $4)
            """,
            created_user.id, test_tenant, "admin", True
        )
    
    yield created_user
    
    # Cleanup handled by tenant deletion


@pytest_asyncio.fixture
async def test_content(test_tenant: str) -> AsyncGenerator[Content, None]:
    """Create test content."""
    content = Content(
        id=str(uuid4()),
        org_id=test_tenant,
        title="Test Content",
        slug="test-content",
        content_type="article",
        status="draft",
        language="en",
        target_keywords=["test", "content"]
    )
    
    created_content = await db_manager.postgresql.create(content, test_tenant)
    
    # Create MongoDB document
    mongo_doc = ContentDocument(
        org_id=test_tenant,
        postgres_content_id=str(created_content.id),
        title=created_content.title,
        slug=created_content.slug,
        content_type="article"
    )
    
    await db_manager.mongodb.create(mongo_doc, test_tenant)
    
    yield created_content
    
    # Cleanup handled by tenant deletion


@pytest.fixture
def mock_redis_data():
    """Mock data for Redis tests."""
    return {
        "session_data": {
            "user_id": str(uuid4()),
            "expires_at": "2024-12-31T23:59:59Z",
            "permissions": ["read", "write"]
        },
        "cache_data": {
            "result": "cached_value",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    }


@pytest.fixture
def mock_neo4j_data():
    """Mock data for Neo4j tests."""
    return {
        "content_node": {
            "uid": str(uuid4()),
            "title": "Test Content",
            "content_type": "article",
            "optimization_score": 85.5
        },
        "topic_node": {
            "uid": "topic_test",
            "name": "Test Topic",
            "category": "Technology",
            "search_volume": 10000
        },
        "keyword_node": {
            "uid": "keyword_test",
            "keyword": "test keyword",
            "search_volume": 5000,
            "difficulty_score": 45.0
        }
    }