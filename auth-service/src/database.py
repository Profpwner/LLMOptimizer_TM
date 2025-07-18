"""Database connection and session management for auth service."""

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import redis.asyncio as redis

from .config import settings

# Create async engine
if settings.ENVIRONMENT == "test":
    engine = create_async_engine(
        settings.POSTGRES_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        poolclass=NullPool
    )
else:
    engine = create_async_engine(
        settings.POSTGRES_URL,
        echo=settings.DEBUG,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True
    )

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Redis client
redis_client = None


async def init_db():
    """Initialize database tables."""
    from .models import Base
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> redis.Redis:
    """Get Redis client."""
    global redis_client
    
    if not redis_client:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    return redis_client


@asynccontextmanager
async def get_db_context():
    """Get database session context manager."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_connections():
    """Close all database connections."""
    await engine.dispose()
    
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None