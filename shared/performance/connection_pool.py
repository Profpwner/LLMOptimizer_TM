"""
Database connection pooling for high-performance database access.
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
import asyncpg
import redis
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase
import logging

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """
    Manages connection pools for all databases with optimization for 100K+ concurrent users.
    """
    
    def __init__(self):
        self.pools: Dict[str, Any] = {}
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load connection pool configuration."""
        return {
            'postgresql': {
                'min_size': int(os.getenv('PG_POOL_MIN_SIZE', '20')),
                'max_size': int(os.getenv('PG_POOL_MAX_SIZE', '100')),
                'max_queries': int(os.getenv('PG_POOL_MAX_QUERIES', '50000')),
                'max_inactive_connection_lifetime': float(os.getenv('PG_POOL_MAX_INACTIVE_LIFETIME', '300')),
                'command_timeout': float(os.getenv('PG_COMMAND_TIMEOUT', '10')),
                'server_settings': {
                    'application_name': 'llmoptimizer',
                    'jit': 'off'  # Disable JIT for predictable performance
                }
            },
            'redis': {
                'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '1000')),
                'socket_keepalive': True,
                'socket_keepalive_options': {
                    1: 3,  # TCP_KEEPIDLE
                    2: 3,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                },
                'decode_responses': True,
                'health_check_interval': 30
            },
            'mongodb': {
                'minPoolSize': int(os.getenv('MONGO_MIN_POOL_SIZE', '20')),
                'maxPoolSize': int(os.getenv('MONGO_MAX_POOL_SIZE', '100')),
                'maxIdleTimeMS': int(os.getenv('MONGO_MAX_IDLE_TIME_MS', '60000')),
                'waitQueueTimeoutMS': int(os.getenv('MONGO_WAIT_QUEUE_TIMEOUT_MS', '5000')),
                'serverSelectionTimeoutMS': int(os.getenv('MONGO_SERVER_SELECTION_TIMEOUT_MS', '5000')),
                'connectTimeoutMS': int(os.getenv('MONGO_CONNECT_TIMEOUT_MS', '10000')),
                'socketTimeoutMS': int(os.getenv('MONGO_SOCKET_TIMEOUT_MS', '10000')),
                'compressors': ['zstd', 'zlib', 'snappy'],
                'retryWrites': True,
                'retryReads': True
            },
            'neo4j': {
                'max_connection_pool_size': int(os.getenv('NEO4J_MAX_POOL_SIZE', '100')),
                'connection_acquisition_timeout': float(os.getenv('NEO4J_CONNECTION_TIMEOUT', '60')),
                'max_connection_lifetime': int(os.getenv('NEO4J_MAX_CONNECTION_LIFETIME', '3600')),
                'connection_timeout': float(os.getenv('NEO4J_CONNECTION_TIMEOUT', '30')),
                'keep_alive': True
            }
        }
    
    async def initialize_postgresql(self, dsn: str) -> asyncpg.Pool:
        """Initialize PostgreSQL connection pool with pgbouncer-like features."""
        try:
            pool = await asyncpg.create_pool(
                dsn,
                **self.config['postgresql'],
                init=self._init_postgresql_connection
            )
            self.pools['postgresql'] = pool
            logger.info("PostgreSQL connection pool initialized")
            return pool
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise
    
    async def _init_postgresql_connection(self, conn):
        """Initialize PostgreSQL connection with optimizations."""
        # Set statement timeout
        await conn.execute("SET statement_timeout = '30s'")
        # Enable query planning optimizations
        await conn.execute("SET random_page_cost = 1.1")
        await conn.execute("SET effective_cache_size = '4GB'")
        # Prepared statements for common queries
        await conn.execute("SET plan_cache_mode = 'force_generic_plan'")
    
    def initialize_redis(self, url: str) -> redis.asyncio.ConnectionPool:
        """Initialize Redis connection pool."""
        pool = redis.asyncio.ConnectionPool.from_url(
            url,
            **self.config['redis']
        )
        self.pools['redis'] = pool
        logger.info("Redis connection pool initialized")
        return pool
    
    def initialize_mongodb(self, uri: str) -> AsyncIOMotorClient:
        """Initialize MongoDB connection pool."""
        client = AsyncIOMotorClient(
            uri,
            **self.config['mongodb']
        )
        self.pools['mongodb'] = client
        logger.info("MongoDB connection pool initialized")
        return client
    
    async def initialize_neo4j(self, uri: str, auth: tuple) -> AsyncGraphDatabase.driver:
        """Initialize Neo4j connection pool."""
        driver = AsyncGraphDatabase.driver(
            uri,
            auth=auth,
            **self.config['neo4j']
        )
        self.pools['neo4j'] = driver
        logger.info("Neo4j connection pool initialized")
        return driver
    
    @asynccontextmanager
    async def get_postgresql_connection(self):
        """Get PostgreSQL connection from pool."""
        pool = self.pools.get('postgresql')
        if not pool:
            raise RuntimeError("PostgreSQL pool not initialized")
        
        async with pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def get_redis_connection(self):
        """Get Redis connection from pool."""
        pool = self.pools.get('redis')
        if not pool:
            raise RuntimeError("Redis pool not initialized")
        
        client = redis.asyncio.Redis(connection_pool=pool)
        try:
            yield client
        finally:
            await client.close()
    
    def get_mongodb_client(self) -> AsyncIOMotorClient:
        """Get MongoDB client."""
        client = self.pools.get('mongodb')
        if not client:
            raise RuntimeError("MongoDB client not initialized")
        return client
    
    def get_neo4j_driver(self) -> AsyncGraphDatabase.driver:
        """Get Neo4j driver."""
        driver = self.pools.get('neo4j')
        if not driver:
            raise RuntimeError("Neo4j driver not initialized")
        return driver
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all connection pools."""
        health = {}
        
        # PostgreSQL health check
        if 'postgresql' in self.pools:
            try:
                async with self.get_postgresql_connection() as conn:
                    await conn.fetchval("SELECT 1")
                health['postgresql'] = True
            except Exception:
                health['postgresql'] = False
        
        # Redis health check
        if 'redis' in self.pools:
            try:
                async with self.get_redis_connection() as conn:
                    await conn.ping()
                health['redis'] = True
            except Exception:
                health['redis'] = False
        
        # MongoDB health check
        if 'mongodb' in self.pools:
            try:
                client = self.get_mongodb_client()
                await client.admin.command('ping')
                health['mongodb'] = True
            except Exception:
                health['mongodb'] = False
        
        # Neo4j health check
        if 'neo4j' in self.pools:
            try:
                driver = self.get_neo4j_driver()
                async with driver.session() as session:
                    await session.run("RETURN 1")
                health['neo4j'] = True
            except Exception:
                health['neo4j'] = False
        
        return health
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics for all connection pools."""
        stats = {}
        
        if 'postgresql' in self.pools:
            pool = self.pools['postgresql']
            stats['postgresql'] = {
                'size': pool.get_size(),
                'idle': pool.get_idle_size(),
                'max_size': pool.get_max_size(),
                'min_size': pool.get_min_size()
            }
        
        if 'redis' in self.pools:
            pool = self.pools['redis']
            stats['redis'] = {
                'created_connections': pool.created_connections,
                'available_connections': len(pool._available_connections),
                'in_use_connections': len(pool._in_use_connections),
                'max_connections': pool.max_connections
            }
        
        return stats
    
    async def close_all(self):
        """Close all connection pools."""
        if 'postgresql' in self.pools:
            await self.pools['postgresql'].close()
            
        if 'redis' in self.pools:
            await self.pools['redis'].disconnect()
            
        if 'mongodb' in self.pools:
            self.pools['mongodb'].close()
            
        if 'neo4j' in self.pools:
            await self.pools['neo4j'].close()
        
        logger.info("All connection pools closed")


# Global instance
connection_manager = ConnectionPoolManager()


# PgBouncer configuration helper
def generate_pgbouncer_config(databases: List[Dict[str, str]]) -> str:
    """Generate pgbouncer configuration for external pgbouncer instance."""
    config = """
[databases]
"""
    for db in databases:
        config += f"{db['name']} = host={db['host']} port={db['port']} dbname={db['dbname']}\n"
    
    config += """
[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
admin_users = postgres
stats_users = postgres, monitor

# Pool settings optimized for 100K+ users
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 100
min_pool_size = 20
reserve_pool_size = 20
reserve_pool_timeout = 5
max_db_connections = 1000
max_user_connections = 1000

# Timeouts
server_lifetime = 3600
server_idle_timeout = 600
server_connect_timeout = 15
server_login_retry = 15
query_timeout = 0
query_wait_timeout = 120
client_idle_timeout = 0
client_login_timeout = 60
idle_transaction_timeout = 0

# Low-level network settings
pkt_buf = 4096
listen_backlog = 4096
sbuf_loopcnt = 5
tcp_defer_accept = 45
tcp_socket_buffer = 0
tcp_keepalive = 1
tcp_keepcnt = 3
tcp_keepidle = 30
tcp_keepintvl = 10

# Logging
log_connections = 0
log_disconnections = 0
log_pooler_errors = 1
log_stats = 1
stats_period = 60

# Security
server_tls_sslmode = prefer
server_tls_protocols = secure
server_tls_ciphers = HIGH:MEDIUM:+3DES:!aNULL
"""
    return config