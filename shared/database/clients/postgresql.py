"""PostgreSQL client with async support and multi-tenancy."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Type, TypeVar, Union

import asyncpg
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeMeta
from sqlalchemy.pool import NullPool, QueuePool
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import PostgreSQLConfig, db_config

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=DeclarativeMeta)


class PostgreSQLClient:
    """Async PostgreSQL client with connection pooling and multi-tenancy support."""
    
    def __init__(self, config: Optional[PostgreSQLConfig] = None):
        """Initialize PostgreSQL client."""
        self.config = config or db_config.postgresql
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_engine: Optional[Any] = None
        self._async_session_maker: Optional[sessionmaker] = None
        self._sync_session_maker: Optional[sessionmaker] = None
        self._connection_pool: Optional[asyncpg.Pool] = None
        
    async def initialize(self):
        """Initialize database connections and pools."""
        # Create async engine with connection pooling
        self._async_engine = create_async_engine(
            self.config.async_url,
            pool_size=self.config.pool_min_size,
            max_overflow=self.config.pool_max_size - self.config.pool_min_size,
            pool_timeout=self.config.pool_timeout,
            pool_pre_ping=True,
            echo=False,
        )
        
        # Create sync engine for migrations and admin tasks
        self._sync_engine = create_engine(
            self.config.sync_url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            echo=False,
        )
        
        # Create session makers
        self._async_session_maker = sessionmaker(
            self._async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        self._sync_session_maker = sessionmaker(
            self._sync_engine,
            expire_on_commit=False,
        )
        
        # Create raw asyncpg connection pool for performance-critical queries
        self._connection_pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            min_size=self.config.pool_min_size,
            max_size=self.config.pool_max_size,
            timeout=self.config.pool_timeout,
        )
        
        logger.info("PostgreSQL client initialized successfully")
    
    async def close(self):
        """Close all database connections."""
        if self._connection_pool:
            await self._connection_pool.close()
        
        if self._async_engine:
            await self._async_engine.dispose()
        
        if self._sync_engine:
            self._sync_engine.dispose()
        
        logger.info("PostgreSQL client closed")
    
    @asynccontextmanager
    async def get_session(self, tenant_id: Optional[str] = None):
        """Get an async database session with optional tenant context."""
        async with self._async_session_maker() as session:
            try:
                if tenant_id and self.config.enable_row_level_security:
                    # Set tenant context for RLS
                    await session.execute(
                        text("SET LOCAL app.current_tenant = :tenant_id"),
                        {"tenant_id": tenant_id}
                    )
                
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @asynccontextmanager
    async def get_raw_connection(self):
        """Get a raw asyncpg connection for performance-critical queries."""
        async with self._connection_pool.acquire() as connection:
            yield connection
    
    # CRUD Operations
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create(self, model: T, tenant_id: Optional[str] = None) -> T:
        """Create a new record."""
        async with self.get_session(tenant_id) as session:
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return model
    
    async def create_many(self, models: List[T], tenant_id: Optional[str] = None) -> List[T]:
        """Create multiple records in a single transaction."""
        async with self.get_session(tenant_id) as session:
            session.add_all(models)
            await session.flush()
            for model in models:
                await session.refresh(model)
            return models
    
    async def get(self, model_class: Type[T], id: Any, tenant_id: Optional[str] = None) -> Optional[T]:
        """Get a record by ID."""
        async with self.get_session(tenant_id) as session:
            query = session.query(model_class).filter(model_class.id == id)
            
            # Apply tenant filter if needed
            if tenant_id and hasattr(model_class, 'org_id'):
                query = query.filter(model_class.org_id == tenant_id)
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_many(self, model_class: Type[T], filters: Dict[str, Any],
                      tenant_id: Optional[str] = None, limit: int = 100,
                      offset: int = 0, order_by: Optional[str] = None) -> List[T]:
        """Get multiple records with filters."""
        async with self.get_session(tenant_id) as session:
            query = session.query(model_class)
            
            # Apply filters
            for key, value in filters.items():
                if hasattr(model_class, key):
                    query = query.filter(getattr(model_class, key) == value)
            
            # Apply tenant filter
            if tenant_id and hasattr(model_class, 'org_id'):
                query = query.filter(model_class.org_id == tenant_id)
            
            # Apply ordering
            if order_by and hasattr(model_class, order_by):
                query = query.order_by(getattr(model_class, order_by))
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def update(self, model: T, updates: Dict[str, Any], tenant_id: Optional[str] = None) -> T:
        """Update a record."""
        async with self.get_session(tenant_id) as session:
            # Verify tenant access
            if tenant_id and hasattr(model, 'org_id') and model.org_id != tenant_id:
                raise PermissionError("Access denied to this resource")
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(model, key) and key not in ['id', 'created_at', 'org_id']:
                    setattr(model, key, value)
            
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return model
    
    async def delete(self, model: T, tenant_id: Optional[str] = None, soft_delete: bool = True) -> bool:
        """Delete a record (soft delete by default)."""
        async with self.get_session(tenant_id) as session:
            # Verify tenant access
            if tenant_id and hasattr(model, 'org_id') and model.org_id != tenant_id:
                raise PermissionError("Access denied to this resource")
            
            if soft_delete and hasattr(model, 'is_deleted'):
                # Soft delete
                model.is_deleted = True
                model.deleted_at = asyncio.get_event_loop().time()
                session.add(model)
            else:
                # Hard delete
                await session.delete(model)
            
            return True
    
    # Raw Query Execution
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None,
                          tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute a raw SQL query and return results."""
        async with self.get_raw_connection() as connection:
            # Set tenant context if needed
            if tenant_id and self.config.enable_row_level_security:
                await connection.execute(
                    "SET LOCAL app.current_tenant = $1",
                    tenant_id
                )
            
            # Execute query
            rows = await connection.fetch(query, *(params or {}).values())
            return [dict(row) for row in rows]
    
    async def execute_many(self, query: str, params_list: List[Dict[str, Any]],
                         tenant_id: Optional[str] = None) -> int:
        """Execute a query multiple times with different parameters."""
        async with self.get_raw_connection() as connection:
            # Set tenant context
            if tenant_id and self.config.enable_row_level_security:
                await connection.execute(
                    "SET LOCAL app.current_tenant = $1",
                    tenant_id
                )
            
            # Prepare statement
            stmt = await connection.prepare(query)
            
            # Execute for each parameter set
            count = 0
            for params in params_list:
                await stmt.fetch(*params.values())
                count += 1
            
            return count
    
    # Transaction Management
    @asynccontextmanager
    async def transaction(self, tenant_id: Optional[str] = None):
        """Create a database transaction context."""
        async with self.get_session(tenant_id) as session:
            async with session.begin():
                yield session
    
    # Multi-tenancy Helpers
    async def create_tenant_schema(self, tenant_id: str):
        """Create a new schema for a tenant (schema isolation mode)."""
        if self.config.tenant_isolation_mode != "schema":
            return
        
        schema_name = f"tenant_{tenant_id}"
        async with self.get_raw_connection() as connection:
            # Create schema
            await connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            
            # Grant permissions
            await connection.execute(
                f"GRANT ALL ON SCHEMA {schema_name} TO {self.config.user}"
            )
            
            logger.info(f"Created schema for tenant: {schema_name}")
    
    async def enable_rls_for_table(self, table_name: str):
        """Enable row-level security for a table."""
        async with self.get_raw_connection() as connection:
            # Enable RLS
            await connection.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
            
            # Create policy
            policy_name = f"{table_name}_tenant_isolation"
            await connection.execute(f"""
                CREATE POLICY {policy_name} ON {table_name}
                FOR ALL
                USING (org_id = current_setting('app.current_tenant')::uuid)
                WITH CHECK (org_id = current_setting('app.current_tenant')::uuid)
            """)
            
            logger.info(f"Enabled RLS for table: {table_name}")
    
    # Performance Monitoring
    async def get_slow_queries(self, threshold_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get slow queries from pg_stat_statements."""
        threshold = threshold_ms or self.config.slow_query_threshold_ms
        
        query = """
        SELECT 
            query,
            calls,
            total_exec_time,
            mean_exec_time,
            stddev_exec_time,
            rows
        FROM pg_stat_statements
        WHERE mean_exec_time > $1
        ORDER BY mean_exec_time DESC
        LIMIT 50
        """
        
        return await self.execute_query(query, {"threshold": threshold})
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        pool_stats = {
            "pool_size": self._connection_pool.get_size() if self._connection_pool else 0,
            "pool_free": self._connection_pool.get_idle_size() if self._connection_pool else 0,
            "pool_used": (self._connection_pool.get_size() - self._connection_pool.get_idle_size()) 
                        if self._connection_pool else 0,
        }
        
        # Get database connection stats
        query = """
        SELECT 
            state,
            COUNT(*) as count
        FROM pg_stat_activity
        WHERE datname = current_database()
        GROUP BY state
        """
        
        db_stats = await self.execute_query(query)
        
        return {
            "pool": pool_stats,
            "database": {row["state"]: row["count"] for row in db_stats}
        }


# Global client instance
postgresql_client = PostgreSQLClient()