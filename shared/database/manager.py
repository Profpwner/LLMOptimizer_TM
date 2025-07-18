"""Unified database manager for coordinating all database clients."""

import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from .clients.postgresql import postgresql_client, PostgreSQLClient
from .clients.mongodb import mongodb_client, MongoDBClient
from .clients.redis import redis_client, RedisClient
from .clients.neo4j import neo4j_client, Neo4jClient
from .config import DatabaseConfig, db_config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages all database connections and provides unified access."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """Initialize database manager."""
        self.config = config or db_config
        
        # Database clients
        self.postgresql: PostgreSQLClient = postgresql_client
        self.mongodb: MongoDBClient = mongodb_client
        self.redis: RedisClient = redis_client
        self.neo4j: Neo4jClient = neo4j_client
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize all database connections."""
        if self._initialized:
            return
        
        logger.info("Initializing database connections...")
        
        # Initialize all clients
        await self.postgresql.initialize()
        await self.mongodb.initialize()
        await self.redis.initialize()
        await self.neo4j.initialize()
        
        self._initialized = True
        logger.info("All database connections initialized successfully")
    
    async def close(self):
        """Close all database connections."""
        logger.info("Closing database connections...")
        
        await self.postgresql.close()
        await self.mongodb.close()
        await self.redis.close()
        await self.neo4j.close()
        
        self._initialized = False
        logger.info("All database connections closed")
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all database connections."""
        health = {}
        
        # PostgreSQL health check
        try:
            async with self.postgresql.get_session() as session:
                await session.execute("SELECT 1")
            health["postgresql"] = True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            health["postgresql"] = False
        
        # MongoDB health check
        try:
            await self.mongodb._client.admin.command('ping')
            health["mongodb"] = True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            health["mongodb"] = False
        
        # Redis health check
        try:
            await self.redis._client.ping()
            health["redis"] = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health["redis"] = False
        
        # Neo4j health check
        try:
            await self.neo4j._driver.verify_connectivity()
            health["neo4j"] = True
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            health["neo4j"] = False
        
        return health
    
    # Tenant Management
    async def create_tenant(self, tenant_id: str, organization_data: Dict[str, Any]) -> bool:
        """Create a new tenant across all databases."""
        try:
            # PostgreSQL: Create organization record
            from database.schemas.postgresql.models import Organization
            org = Organization(id=tenant_id, **organization_data)
            await self.postgresql.create(org)
            
            # PostgreSQL: Create schema if using schema isolation
            if self.config.postgresql.tenant_isolation_mode == "schema":
                await self.postgresql.create_tenant_schema(tenant_id)
            
            # MongoDB: Create initial collections with indexes
            # Collections are created automatically on first use
            
            # Redis: Set up tenant configuration
            tenant_config = self.config.get_tenant_config(tenant_id)
            await self.redis.set_json(
                f"tenant:config:{tenant_id}",
                tenant_config,
                tenant_id=None  # Store in global namespace
            )
            
            # Neo4j: Create tenant root node
            await self.neo4j.create_node(
                {
                    "uid": tenant_id,
                    "name": organization_data.get("name"),
                    "created_at": "datetime()"
                },
                ["Organization"],
                tenant_id
            )
            
            logger.info(f"Tenant {tenant_id} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create tenant {tenant_id}: {e}")
            # TODO: Implement rollback logic
            raise
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant and all associated data."""
        try:
            # Neo4j: Delete all tenant nodes and relationships
            await self.neo4j._driver.session().run(
                "MATCH (n {org_id: $org_id}) DETACH DELETE n",
                org_id=tenant_id
            )
            
            # Redis: Flush all tenant keys
            deleted_keys = await self.redis.flush_tenant(tenant_id)
            logger.info(f"Deleted {deleted_keys} Redis keys for tenant {tenant_id}")
            
            # MongoDB: Drop tenant collections or delete documents
            if self.config.mongodb.tenant_collection_prefix:
                # Drop prefixed collections
                collections = await self.mongodb._database.list_collection_names()
                for collection in collections:
                    if collection.startswith(f"tenant_{tenant_id}_"):
                        await self.mongodb._database.drop_collection(collection)
            else:
                # Delete documents by org_id
                for model in [ContentDocument, OptimizationResult, AnalyticsEvent]:
                    await self.mongodb.delete_many(model, {"org_id": tenant_id})
            
            # PostgreSQL: Delete or archive tenant data
            # This depends on your data retention policy
            # For now, we'll soft delete the organization
            org = await self.postgresql.get(Organization, tenant_id)
            if org:
                await self.postgresql.delete(org, soft_delete=True)
            
            logger.info(f"Tenant {tenant_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            raise
    
    # Cross-Database Operations
    async def get_content_full_data(self, content_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get complete content data from all databases."""
        result = {}
        
        # PostgreSQL: Get core content record
        from database.schemas.postgresql.models import Content
        content = await self.postgresql.get(Content, content_id, tenant_id)
        if not content:
            return None
        
        result["core"] = content.to_dict()
        
        # MongoDB: Get content document with versions
        if content.mongodb_id:
            mongo_content = await self.mongodb.get(
                ContentDocument,
                content.mongodb_id,
                tenant_id
            )
            if mongo_content:
                result["document"] = mongo_content.dict()
        
        # Redis: Get cached data
        cache_key = f"content:{content_id}:cache"
        cached_data = await self.redis.get_json(cache_key, tenant_id)
        if cached_data:
            result["cached"] = cached_data
        
        # Neo4j: Get knowledge graph connections
        graph_data = await self.neo4j.find_connected_nodes(
            content_id,
            "Content",
            tenant_id=tenant_id
        )
        result["graph"] = graph_data
        
        return result
    
    async def cache_query_result(self, query_key: str, result: Any,
                               tenant_id: str, ttl: int = 3600) -> bool:
        """Cache a query result across appropriate databases."""
        # Use Redis for simple caching
        if isinstance(result, (dict, list)):
            return await self.redis.set_json(query_key, result, tenant_id, ttl)
        else:
            return await self.redis.set_object(query_key, result, tenant_id, ttl)
    
    @asynccontextmanager
    async def distributed_transaction(self, tenant_id: str):
        """
        Create a distributed transaction context.
        Note: This is a simplified version. Full distributed transactions
        would require two-phase commit or saga pattern.
        """
        # Start transactions in all databases that support them
        pg_session = None
        neo4j_session = None
        
        try:
            # PostgreSQL transaction
            pg_session = self.postgresql.get_session(tenant_id)
            await pg_session.__aenter__()
            
            # Neo4j transaction
            neo4j_session = self.neo4j.get_session()
            await neo4j_session.__aenter__()
            
            yield {
                "postgresql": pg_session,
                "neo4j": neo4j_session,
                "mongodb": self.mongodb,  # MongoDB handles transactions differently
                "redis": self.redis  # Redis doesn't have traditional transactions
            }
            
            # Commit all transactions
            await pg_session.__aexit__(None, None, None)
            await neo4j_session.__aexit__(None, None, None)
            
        except Exception as e:
            # Rollback on error
            if pg_session:
                await pg_session.__aexit__(type(e), e, e.__traceback__)
            if neo4j_session:
                await neo4j_session.__aexit__(type(e), e, e.__traceback__)
            raise
    
    # Performance Monitoring
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from all databases."""
        metrics = {}
        
        # PostgreSQL metrics
        metrics["postgresql"] = {
            "slow_queries": await self.postgresql.get_slow_queries(),
            "connection_stats": await self.postgresql.get_connection_stats()
        }
        
        # MongoDB metrics
        metrics["mongodb"] = {
            "slow_queries": await self.mongodb.get_slow_queries()
        }
        
        # Redis metrics
        metrics["redis"] = await self.redis.get_info()
        
        # Neo4j metrics
        # Neo4j metrics would be retrieved here
        
        return metrics
    
    # Backup Operations
    async def backup_tenant_data(self, tenant_id: str) -> Dict[str, Any]:
        """Create a backup of all tenant data."""
        backup = {}
        
        # PostgreSQL: Export using pg_dump would be done separately
        # Here we just export the data as JSON
        from database.schemas.postgresql.models import Content, ContentOptimization
        
        contents = await self.postgresql.get_many(
            Content,
            {"org_id": tenant_id},
            tenant_id
        )
        backup["postgresql"] = {
            "contents": [c.to_dict() for c in contents]
        }
        
        # MongoDB: Export collections
        from database.schemas.mongodb.models import ContentDocument
        backup["mongodb"] = {
            "contents": await self.mongodb.export_collection(
                ContentDocument,
                tenant_id
            )
        }
        
        # Neo4j: Export graph
        async with self.neo4j.get_session() as session:
            result = await session.run(
                """
                MATCH (n {org_id: $org_id})
                OPTIONAL MATCH (n)-[r]-(m {org_id: $org_id})
                RETURN collect(DISTINCT n) as nodes, collect(DISTINCT r) as relationships
                """,
                org_id=tenant_id
            )
            record = await result.single()
            backup["neo4j"] = {
                "nodes": [dict(n) for n in record["nodes"]],
                "relationships": [dict(r) for r in record["relationships"] if r]
            }
        
        return backup


# Global database manager instance
db_manager = DatabaseManager()


# Convenience function for service initialization
async def initialize_databases():
    """Initialize all database connections."""
    await db_manager.initialize()


async def close_databases():
    """Close all database connections."""
    await db_manager.close()