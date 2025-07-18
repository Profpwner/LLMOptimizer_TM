"""
Redis caching implementation with advanced features.
"""

import asyncio
import json
import pickle
import time
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass
import redis.asyncio as redis
from redis.asyncio.sentinel import Sentinel
import msgpack
import logging

logger = logging.getLogger(__name__)


@dataclass
class RedisCacheConfig:
    """Redis cache configuration."""
    # Connection settings
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    
    # Connection pool settings
    max_connections: int = 1000
    connection_pool_class: str = "redis.asyncio.ConnectionPool"
    
    # Cluster/Sentinel settings
    enable_cluster: bool = False
    enable_sentinel: bool = False
    sentinel_hosts: List[tuple] = None
    sentinel_service_name: str = "mymaster"
    
    # Performance settings
    socket_keepalive: bool = True
    socket_keepalive_options: Dict[int, int] = None
    socket_connect_timeout: int = 20
    socket_timeout: int = 20
    
    # Serialization
    serializer: str = "msgpack"  # "json", "pickle", "msgpack"
    compression: bool = True
    
    # Key settings
    key_prefix: str = "llmopt:"
    default_ttl: int = 300
    
    # Advanced features
    enable_pipeline: bool = True
    pipeline_batch_size: int = 100
    enable_lua_scripts: bool = True
    enable_memory_optimization: bool = True


class RedisCache:
    """
    High-performance Redis cache implementation for 100K+ concurrent users.
    """
    
    def __init__(self, config: Optional[RedisCacheConfig] = None):
        self.config = config or RedisCacheConfig()
        self.client: Optional[redis.Redis] = None
        self.sentinel: Optional[Sentinel] = None
        
        # Serialization methods
        self.serializers = {
            'json': (json.dumps, json.loads),
            'pickle': (pickle.dumps, pickle.loads),
            'msgpack': (msgpack.packb, msgpack.unpackb)
        }
        
        # Lua scripts
        self.scripts = {}
        self._register_lua_scripts()
        
        # Pipeline for batch operations
        self.pipeline_queue: List[tuple] = []
        self.pipeline_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize Redis connection."""
        if self.config.socket_keepalive_options is None:
            self.config.socket_keepalive_options = {
                1: 1,  # TCP_KEEPIDLE
                2: 1,  # TCP_KEEPINTVL
                3: 3,  # TCP_KEEPCNT
            }
        
        if self.config.enable_sentinel:
            await self._init_sentinel()
        elif self.config.enable_cluster:
            await self._init_cluster()
        else:
            await self._init_standalone()
        
        # Start pipeline processor if enabled
        if self.config.enable_pipeline:
            self.pipeline_task = asyncio.create_task(self._pipeline_processor())
        
        logger.info("Redis cache initialized")
    
    async def _init_standalone(self):
        """Initialize standalone Redis connection."""
        pool = redis.ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            db=self.config.db,
            max_connections=self.config.max_connections,
            decode_responses=False,  # We handle encoding/decoding
            socket_keepalive=self.config.socket_keepalive,
            socket_keepalive_options=self.config.socket_keepalive_options,
            socket_connect_timeout=self.config.socket_connect_timeout,
            socket_timeout=self.config.socket_timeout
        )
        
        self.client = redis.Redis(connection_pool=pool)
        
        # Test connection
        await self.client.ping()
    
    async def _init_sentinel(self):
        """Initialize Redis Sentinel connection."""
        if not self.config.sentinel_hosts:
            raise ValueError("Sentinel hosts not configured")
        
        self.sentinel = Sentinel(
            self.config.sentinel_hosts,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            socket_keepalive=self.config.socket_keepalive,
            socket_keepalive_options=self.config.socket_keepalive_options
        )
        
        # Get master connection
        self.client = self.sentinel.master_for(
            self.config.sentinel_service_name,
            redis_class=redis.Redis,
            connection_pool_class=redis.AsyncSentinelConnectionPool,
            max_connections=self.config.max_connections,
            decode_responses=False
        )
        
        await self.client.ping()
    
    async def _init_cluster(self):
        """Initialize Redis Cluster connection."""
        # Import cluster support
        from redis.asyncio.cluster import RedisCluster
        
        self.client = RedisCluster(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            decode_responses=False,
            max_connections=self.config.max_connections,
            socket_keepalive=self.config.socket_keepalive,
            socket_keepalive_options=self.config.socket_keepalive_options
        )
        
        await self.client.ping()
    
    def _register_lua_scripts(self):
        """Register Lua scripts for atomic operations."""
        # Conditional set with TTL
        self.scripts['conditional_set'] = """
        local key = KEYS[1]
        local value = ARGV[1]
        local ttl = ARGV[2]
        local condition = ARGV[3]
        
        if condition == 'nx' then
            if redis.call('EXISTS', key) == 0 then
                return redis.call('SETEX', key, ttl, value)
            end
        elseif condition == 'xx' then
            if redis.call('EXISTS', key) == 1 then
                return redis.call('SETEX', key, ttl, value)
            end
        else
            return redis.call('SETEX', key, ttl, value)
        end
        
        return nil
        """
        
        # Batch increment with expiry
        self.scripts['batch_incr'] = """
        local results = {}
        for i = 1, #KEYS do
            local count = redis.call('INCR', KEYS[i])
            redis.call('EXPIRE', KEYS[i], ARGV[1])
            table.insert(results, count)
        end
        return results
        """
        
        # Get and extend TTL
        self.scripts['get_extend_ttl'] = """
        local key = KEYS[1]
        local extend_by = tonumber(ARGV[1])
        
        local value = redis.call('GET', key)
        if value then
            local ttl = redis.call('TTL', key)
            if ttl > 0 then
                redis.call('EXPIRE', key, ttl + extend_by)
            end
        end
        
        return value
        """
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self.config.key_prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        serializer, _ = self.serializers[self.config.serializer]
        
        if self.config.serializer == 'msgpack':
            data = serializer(value, use_bin_type=True)
        else:
            data = serializer(value)
            if isinstance(data, str):
                data = data.encode('utf-8')
        
        if self.config.compression and len(data) > 1024:
            import gzip
            data = gzip.compress(data)
        
        return data
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if not data:
            return None
        
        # Check if compressed
        if self.config.compression and data[:2] == b'\x1f\x8b':
            import gzip
            data = gzip.decompress(data)
        
        _, deserializer = self.serializers[self.config.serializer]
        
        if self.config.serializer == 'json':
            return deserializer(data.decode('utf-8'))
        else:
            return deserializer(data)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            full_key = self._make_key(key)
            data = await self.client.get(full_key)
            
            if data is None:
                return None
            
            return self._deserialize(data)
            
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists
        """
        try:
            full_key = self._make_key(key)
            ttl = ttl or self.config.default_ttl
            data = self._serialize(value)
            
            if self.config.enable_lua_scripts and (nx or xx):
                # Use Lua script for conditional set
                condition = 'nx' if nx else 'xx' if xx else 'none'
                script = self.client.register_script(self.scripts['conditional_set'])
                result = await script(keys=[full_key], args=[data, ttl, condition])
                return result is not None
            else:
                # Standard set
                return await self.client.setex(full_key, ttl, data)
                
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            full_key = self._make_key(key)
            result = await self.client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            full_key = self._make_key(key)
            return await self.client.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        try:
            full_key = self._make_key(key)
            return await self.client.ttl(full_key)
        except Exception as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            return -1
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key."""
        try:
            full_key = self._make_key(key)
            return await self.client.expire(full_key, ttl)
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False
    
    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values."""
        try:
            full_keys = [self._make_key(key) for key in keys]
            values = await self.client.mget(full_keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)
            
            return result
            
        except Exception as e:
            logger.error(f"Redis mget error: {e}")
            return {}
    
    async def mset(self, items: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values."""
        try:
            ttl = ttl or self.config.default_ttl
            
            # Prepare data
            mapping = {}
            for key, value in items.items():
                full_key = self._make_key(key)
                mapping[full_key] = self._serialize(value)
            
            # Use pipeline for atomic operation
            async with self.client.pipeline(transaction=True) as pipe:
                await pipe.mset(mapping)
                
                # Set TTL for each key
                for full_key in mapping.keys():
                    await pipe.expire(full_key, ttl)
                
                await pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Redis mset error: {e}")
            return False
    
    async def incr(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment counter."""
        try:
            full_key = self._make_key(key)
            ttl = ttl or self.config.default_ttl
            
            if self.config.enable_lua_scripts and ttl:
                # Use Lua script to increment and set TTL atomically
                script = self.client.register_script(self.scripts['batch_incr'])
                results = await script(keys=[full_key], args=[ttl])
                return results[0] if results else 0
            else:
                # Standard increment
                value = await self.client.incrby(full_key, amount)
                if ttl:
                    await self.client.expire(full_key, ttl)
                return value
                
        except Exception as e:
            logger.error(f"Redis incr error for key {key}: {e}")
            return 0
    
    async def get_extend_ttl(self, key: str, extend_by: int = 300) -> Optional[Any]:
        """Get value and extend its TTL."""
        try:
            full_key = self._make_key(key)
            
            if self.config.enable_lua_scripts:
                script = self.client.register_script(self.scripts['get_extend_ttl'])
                data = await script(keys=[full_key], args=[extend_by])
                
                if data:
                    return self._deserialize(data)
            else:
                # Non-atomic version
                data = await self.client.get(full_key)
                if data:
                    ttl = await self.client.ttl(full_key)
                    if ttl > 0:
                        await self.client.expire(full_key, ttl + extend_by)
                    return self._deserialize(data)
            
            return None
            
        except Exception as e:
            logger.error(f"Redis get_extend_ttl error for key {key}: {e}")
            return None
    
    async def clear(self, pattern: Optional[str] = None):
        """Clear cache entries matching pattern."""
        try:
            if pattern:
                full_pattern = self._make_key(pattern)
            else:
                full_pattern = f"{self.config.key_prefix}*"
            
            # Use SCAN for memory efficiency with large keyspaces
            cursor = 0
            batch_size = 1000
            
            while True:
                cursor, keys = await self.client.scan(
                    cursor,
                    match=full_pattern,
                    count=batch_size
                )
                
                if keys:
                    await self.client.delete(*keys)
                
                if cursor == 0:
                    break
                    
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    async def _pipeline_processor(self):
        """Process pipeline queue for batch operations."""
        while True:
            try:
                if not self.pipeline_queue:
                    await asyncio.sleep(0.01)
                    continue
                
                # Collect batch
                batch = []
                while len(batch) < self.config.pipeline_batch_size and self.pipeline_queue:
                    batch.append(self.pipeline_queue.pop(0))
                
                if batch:
                    # Execute batch
                    async with self.client.pipeline(transaction=False) as pipe:
                        futures = []
                        
                        for cmd, args, future in batch:
                            if cmd == 'get':
                                pipe.get(args[0])
                            elif cmd == 'set':
                                pipe.setex(args[0], args[2], args[1])
                            elif cmd == 'delete':
                                pipe.delete(args[0])
                            
                            futures.append(future)
                        
                        results = await pipe.execute()
                        
                        # Set results
                        for future, result in zip(futures, results):
                            future.set_result(result)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pipeline processor error: {e}")
    
    async def shutdown(self):
        """Shutdown Redis connection."""
        if self.pipeline_task:
            self.pipeline_task.cancel()
        
        if self.client:
            await self.client.close()
        
        logger.info("Redis cache shutdown complete")
    
    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """Get Redis server information."""
        try:
            info = await self.client.info()
            
            return {
                'version': info.get('redis_version'),
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': info.get('used_memory_human'),
                'used_memory_peak_human': info.get('used_memory_peak_human'),
                'total_commands_processed': info.get('total_commands_processed'),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'evicted_keys': info.get('evicted_keys')
            }
        except Exception as e:
            logger.error(f"Redis info error: {e}")
            return {}