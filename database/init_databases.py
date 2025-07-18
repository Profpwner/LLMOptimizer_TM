"""Initialize all databases with schemas and seed data."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from shared.database.manager import db_manager
from shared.database.config import db_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_postgresql_schema():
    """Create PostgreSQL schema and tables."""
    logger.info("Creating PostgreSQL schema...")
    
    # Import all models to ensure they're registered with SQLAlchemy
    from database.schemas.postgresql.models import (
        Organization, User, APIKey, Content,
        ContentOptimization, UserSession
    )
    from database.schemas.postgresql.base import Base
    
    # Create all tables
    async with db_manager.postgresql._async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("PostgreSQL schema created successfully")


async def enable_row_level_security():
    """Enable RLS on all tenant tables."""
    logger.info("Enabling Row Level Security...")
    
    tenant_tables = [
        "api_keys",
        "content",
        "content_optimizations"
    ]
    
    for table in tenant_tables:
        try:
            await db_manager.postgresql.enable_rls_for_table(table)
            logger.info(f"RLS enabled for table: {table}")
        except Exception as e:
            logger.warning(f"Could not enable RLS for {table}: {e}")


async def create_mongodb_indexes():
    """Ensure MongoDB indexes are created."""
    logger.info("Creating MongoDB indexes...")
    
    # Indexes are created automatically by Beanie during initialization
    # Additional custom indexes can be added here if needed
    
    logger.info("MongoDB indexes created successfully")


async def create_neo4j_constraints():
    """Create Neo4j constraints and indexes."""
    logger.info("Creating Neo4j constraints and indexes...")
    
    # Constraints and indexes are created during client initialization
    # Additional custom constraints can be added here
    
    logger.info("Neo4j constraints created successfully")


async def create_demo_tenant():
    """Create a demo tenant for testing."""
    logger.info("Creating demo tenant...")
    
    demo_org_id = "550e8400-e29b-41d4-a716-446655440000"
    
    # Check if demo tenant already exists
    from database.schemas.postgresql.models import Organization
    existing = await db_manager.postgresql.get(Organization, demo_org_id)
    
    if existing:
        logger.info("Demo tenant already exists")
        return demo_org_id
    
    # Create demo organization
    demo_org_data = {
        "name": "Demo Organization",
        "slug": "demo-org",
        "description": "Demo organization for testing",
        "plan_type": "professional",
        "max_users": 10,
        "max_content_items": 1000,
        "max_api_calls_per_month": 100000,
        "storage_quota_gb": 100.0,
        "is_active": True,
        "is_verified": True
    }
    
    await db_manager.create_tenant(demo_org_id, demo_org_data)
    
    logger.info(f"Demo tenant created: {demo_org_id}")
    return demo_org_id


async def create_demo_user():
    """Create a demo user."""
    logger.info("Creating demo user...")
    
    from database.schemas.postgresql.models import User
    from werkzeug.security import generate_password_hash
    
    demo_user_id = "660e8400-e29b-41d4-a716-446655440001"
    
    # Check if user exists
    existing = await db_manager.postgresql.get(User, demo_user_id)
    if existing:
        logger.info("Demo user already exists")
        return demo_user_id
    
    # Create demo user
    demo_user = User(
        id=demo_user_id,
        email="demo@llmoptimizer.com",
        username="demo_user",
        full_name="Demo User",
        password_hash=generate_password_hash("demo_password"),
        is_email_verified=True,
        is_active=True
    )
    
    await db_manager.postgresql.create(demo_user)
    
    # Link user to demo organization
    demo_org_id = "550e8400-e29b-41d4-a716-446655440000"
    
    async with db_manager.postgresql.get_raw_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_organizations (user_id, organization_id, role, is_primary)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
            """,
            demo_user_id, demo_org_id, "owner", True
        )
    
    logger.info(f"Demo user created: {demo_user_id}")
    return demo_user_id


async def create_demo_content():
    """Create demo content for testing."""
    logger.info("Creating demo content...")
    
    demo_org_id = "550e8400-e29b-41d4-a716-446655440000"
    
    # Create demo content in PostgreSQL
    from database.schemas.postgresql.models import Content
    
    demo_content = Content(
        id="770e8400-e29b-41d4-a716-446655440002",
        org_id=demo_org_id,
        title="10 Best Practices for SEO in 2024",
        slug="10-best-practices-seo-2024",
        content_type="article",
        status="optimized",
        optimization_score=85.5,
        readability_score=92.0,
        seo_score=88.0,
        word_count=1500,
        language="en",
        target_keywords=["SEO", "best practices", "2024", "search engine optimization"]
    )
    
    content = await db_manager.postgresql.create(demo_content, demo_org_id)
    
    # Create corresponding MongoDB document
    from database.schemas.mongodb.models import ContentDocument, ContentVersion
    
    mongo_content = ContentDocument(
        org_id=demo_org_id,
        postgres_content_id=str(content.id),
        title=content.title,
        slug=content.slug,
        content_type="article",
        current_version=1,
        versions=[
            ContentVersion(
                version_number=1,
                created_by=str("660e8400-e29b-41d4-a716-446655440001"),
                title=content.title,
                content="This is demo content about SEO best practices...",
                word_count=1500,
                keywords=content.target_keywords,
                optimization_scores={
                    "seo": 88.0,
                    "readability": 92.0,
                    "overall": 85.5
                }
            )
        ],
        tags=["seo", "marketing", "best-practices"],
        categories=["Digital Marketing", "SEO"]
    )
    
    mongo_doc = await db_manager.mongodb.create(mongo_content, demo_org_id)
    
    # Update PostgreSQL with MongoDB ID
    await db_manager.postgresql.update(
        content,
        {"mongodb_id": str(mongo_doc.id)},
        demo_org_id
    )
    
    # Create Neo4j nodes and relationships
    content_node = await db_manager.neo4j.create_node(
        {
            "uid": str(content.id),
            "content_id": str(content.id),
            "title": content.title,
            "slug": content.slug,
            "content_type": "article",
            "optimization_score": content.optimization_score
        },
        ["Content"],
        demo_org_id
    )
    
    # Create topic nodes
    topic_node = await db_manager.neo4j.create_node(
        {
            "uid": "topic_seo_2024",
            "name": "SEO Best Practices",
            "category": "Digital Marketing",
            "subcategory": "SEO",
            "search_volume": 50000,
            "trend_score": 0.85
        },
        ["Topic"],
        demo_org_id
    )
    
    # Link content to topic
    await db_manager.neo4j.create_relationship(
        str(content.id), "Content",
        "topic_seo_2024", "Topic",
        "HAS_TOPIC",
        {"relevance_score": 0.95},
        demo_org_id
    )
    
    # Cache some data in Redis
    await db_manager.redis.set_json(
        f"content:{content.id}:meta",
        {
            "views": 1523,
            "likes": 89,
            "shares": 34,
            "avg_time_on_page": 245.6
        },
        demo_org_id,
        ttl=86400  # 24 hours
    )
    
    logger.info("Demo content created successfully")


async def initialize_all():
    """Initialize all databases with schema and demo data."""
    try:
        # Initialize database connections
        await db_manager.initialize()
        
        # Check health
        health = await db_manager.health_check()
        logger.info(f"Database health check: {health}")
        
        if not all(health.values()):
            raise Exception("Not all databases are healthy")
        
        # Create schemas
        await create_postgresql_schema()
        await enable_row_level_security()
        await create_mongodb_indexes()
        await create_neo4j_constraints()
        
        # Create demo data
        await create_demo_tenant()
        await create_demo_user()
        await create_demo_content()
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(initialize_all())