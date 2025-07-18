"""Database configuration for multi-tenant architecture."""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class PostgreSQLConfig:
    """PostgreSQL database configuration."""
    
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "llmoptimizer")
    user: str = os.getenv("POSTGRES_USER", "postgres")
    password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    
    # Connection pool settings
    pool_min_size: int = int(os.getenv("POSTGRES_POOL_MIN", "10"))
    pool_max_size: int = int(os.getenv("POSTGRES_POOL_MAX", "100"))
    pool_timeout: int = int(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
    
    # Multi-tenancy settings
    enable_row_level_security: bool = os.getenv("ENABLE_RLS", "true").lower() == "true"
    tenant_isolation_mode: str = os.getenv("TENANT_ISOLATION", "row")  # row, schema, database
    
    @property
    def async_url(self) -> str:
        """Get async database URL for asyncpg."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def sync_url(self) -> str:
        """Get sync database URL for psycopg2."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class MongoDBConfig:
    """MongoDB configuration."""
    
    host: str = os.getenv("MONGODB_HOST", "localhost")
    port: int = int(os.getenv("MONGODB_PORT", "27017"))
    database: str = os.getenv("MONGODB_DB", "llmoptimizer")
    username: Optional[str] = os.getenv("MONGODB_USER")
    password: Optional[str] = os.getenv("MONGODB_PASSWORD")
    
    # Connection pool settings
    max_pool_size: int = int(os.getenv("MONGODB_POOL_SIZE", "100"))
    min_pool_size: int = int(os.getenv("MONGODB_MIN_POOL_SIZE", "10"))
    
    # Multi-tenancy settings
    tenant_collection_prefix: bool = os.getenv("MONGODB_TENANT_PREFIX", "true").lower() == "true"
    
    @property
    def url(self) -> str:
        """Get MongoDB connection URL."""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"mongodb://{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration."""
    
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    password: Optional[str] = os.getenv("REDIS_PASSWORD")
    db: int = int(os.getenv("REDIS_DB", "0"))
    
    # Connection pool settings
    max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "100"))
    
    # Multi-tenancy settings
    tenant_key_prefix: bool = os.getenv("REDIS_TENANT_PREFIX", "true").lower() == "true"
    cache_ttl: int = int(os.getenv("REDIS_CACHE_TTL", "3600"))  # 1 hour default
    
    @property
    def url(self) -> str:
        """Get Redis connection URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class Neo4jConfig:
    """Neo4j configuration."""
    
    host: str = os.getenv("NEO4J_HOST", "localhost")
    bolt_port: int = int(os.getenv("NEO4J_BOLT_PORT", "7687"))
    http_port: int = int(os.getenv("NEO4J_HTTP_PORT", "7474"))
    username: str = os.getenv("NEO4J_USER", "neo4j")
    password: str = os.getenv("NEO4J_PASSWORD", "neo4j")
    
    # Connection pool settings
    max_connection_lifetime: int = int(os.getenv("NEO4J_MAX_CONN_LIFETIME", "3600"))
    max_connection_pool_size: int = int(os.getenv("NEO4J_POOL_SIZE", "50"))
    
    # Multi-tenancy settings
    tenant_label_prefix: bool = os.getenv("NEO4J_TENANT_PREFIX", "true").lower() == "true"
    
    @property
    def bolt_url(self) -> str:
        """Get Neo4j Bolt connection URL."""
        return f"bolt://{self.host}:{self.bolt_port}"
    
    @property
    def http_url(self) -> str:
        """Get Neo4j HTTP connection URL."""
        return f"http://{self.host}:{self.http_port}"


@dataclass
class DatabaseConfig:
    """Unified database configuration."""
    
    postgresql: PostgreSQLConfig = PostgreSQLConfig()
    mongodb: MongoDBConfig = MongoDBConfig()
    redis: RedisConfig = RedisConfig()
    neo4j: Neo4jConfig = Neo4jConfig()
    
    # Global settings
    enable_ssl: bool = os.getenv("DB_ENABLE_SSL", "false").lower() == "true"
    enable_encryption_at_rest: bool = os.getenv("DB_ENCRYPT_AT_REST", "true").lower() == "true"
    enable_audit_logging: bool = os.getenv("DB_AUDIT_LOGGING", "true").lower() == "true"
    
    # Performance settings
    enable_query_caching: bool = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"
    slow_query_threshold_ms: int = int(os.getenv("SLOW_QUERY_THRESHOLD", "1000"))
    
    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant-specific configuration."""
        return {
            "tenant_id": tenant_id,
            "postgresql": {
                "schema": f"tenant_{tenant_id}" if self.postgresql.tenant_isolation_mode == "schema" else None,
                "rls_enabled": self.postgresql.enable_row_level_security,
            },
            "mongodb": {
                "collection_prefix": f"tenant_{tenant_id}_" if self.mongodb.tenant_collection_prefix else "",
            },
            "redis": {
                "key_prefix": f"tenant:{tenant_id}:" if self.redis.tenant_key_prefix else "",
            },
            "neo4j": {
                "label_prefix": f"Tenant_{tenant_id}_" if self.neo4j.tenant_label_prefix else "",
            }
        }


# Global configuration instance
db_config = DatabaseConfig()