"""Redis client with async support and multi-tenancy."""

import json
import logging
import pickle
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict, List, Set, Union, Callable
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import RedisConfig, db_config

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client with connection pooling and multi-tenancy support."""
    
    def __init__(self, config: Optional[RedisConfig] = None):
        """Initialize Redis client."""
        self.config = config or db_config.redis
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        
    async def initialize(self):
        """Initialize Redis connection pool."""
        # Create connection pool
        self._pool = ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            db=self.config.db,
            max_connections=self.config.max_connections,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        
        # Create Redis client
        self._client = Redis(connection_pool=self._pool)
        
        # Test connection
        await self._client.ping()
        
        logger.info("Redis client initialized successfully")
    
    async def close(self):
        """Close Redis connection pool."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis client closed")
    
    def _get_key(self, key: str, tenant_id: Optional[str] = None) -> str:
        """Get key with optional tenant prefix."""
        if tenant_id and self.config.tenant_key_prefix:
            return f"tenant:{tenant_id}:{key}"
        return key
    
    # Basic Operations
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get(self, key: str, tenant_id: Optional[str] = None) -> Optional[str]:
        """Get a value by key."""
        full_key = self._get_key(key, tenant_id)
        return await self._client.get(full_key)
    
    async def set(self, key: str, value: Union[str, int, float], 
                  tenant_id: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """Set a value with optional TTL."""
        full_key = self._get_key(key, tenant_id)
        ttl = ttl or self.config.cache_ttl
        
        return await self._client.set(full_key, value, ex=ttl)
    
    async def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete a key."""
        full_key = self._get_key(key, tenant_id)
        return bool(await self._client.delete(full_key))
    
    async def exists(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if a key exists."""
        full_key = self._get_key(key, tenant_id)
        return bool(await self._client.exists(full_key))
    
    async def expire(self, key: str, ttl: int, tenant_id: Optional[str] = None) -> bool:
        """Set expiration time for a key."""
        full_key = self._get_key(key, tenant_id)
        return await self._client.expire(full_key, ttl)
    
    async def ttl(self, key: str, tenant_id: Optional[str] = None) -> int:
        """Get time to live for a key."""
        full_key = self._get_key(key, tenant_id)
        return await self._client.ttl(full_key)
    
    # JSON Operations
    async def get_json(self, key: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get and deserialize JSON value."""
        value = await self.get(key, tenant_id)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key: {key}")
                return None
        return None
    
    async def set_json(self, key: str, value: Dict[str, Any],
                      tenant_id: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """Serialize and set JSON value."""
        json_str = json.dumps(value)
        return await self.set(key, json_str, tenant_id, ttl)
    
    # Binary Operations (for complex objects)
    async def get_object(self, key: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        """Get and deserialize a pickled object."""
        full_key = self._get_key(key, tenant_id)
        value = await self._client.get(full_key)
        if value:
            try:
                return pickle.loads(value.encode('latin-1') if isinstance(value, str) else value)
            except Exception as e:
                logger.error(f"Failed to unpickle object for key {key}: {e}")
                return None
        return None
    
    async def set_object(self, key: str, value: Any,
                        tenant_id: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """Pickle and set an object."""
        full_key = self._get_key(key, tenant_id)
        ttl = ttl or self.config.cache_ttl
        
        pickled = pickle.dumps(value)
        return await self._client.set(full_key, pickled, ex=ttl)
    
    # Hash Operations
    async def hget(self, hash_key: str, field: str, tenant_id: Optional[str] = None) -> Optional[str]:
        """Get a field from a hash."""
        full_key = self._get_key(hash_key, tenant_id)
        return await self._client.hget(full_key, field)
    
    async def hset(self, hash_key: str, field: str, value: str,
                   tenant_id: Optional[str] = None) -> bool:
        """Set a field in a hash."""
        full_key = self._get_key(hash_key, tenant_id)
        return bool(await self._client.hset(full_key, field, value))
    
    async def hgetall(self, hash_key: str, tenant_id: Optional[str] = None) -> Dict[str, str]:
        """Get all fields from a hash."""
        full_key = self._get_key(hash_key, tenant_id)
        return await self._client.hgetall(full_key)
    
    async def hmset(self, hash_key: str, mapping: Dict[str, str],
                    tenant_id: Optional[str] = None) -> bool:
        """Set multiple fields in a hash."""
        full_key = self._get_key(hash_key, tenant_id)
        return await self._client.hset(full_key, mapping=mapping)
    
    async def hdel(self, hash_key: str, *fields: str, tenant_id: Optional[str] = None) -> int:
        """Delete fields from a hash."""
        full_key = self._get_key(hash_key, tenant_id)
        return await self._client.hdel(full_key, *fields)
    
    # List Operations
    async def lpush(self, list_key: str, *values: str, tenant_id: Optional[str] = None) -> int:
        """Push values to the left of a list."""
        full_key = self._get_key(list_key, tenant_id)
        return await self._client.lpush(full_key, *values)
    
    async def rpush(self, list_key: str, *values: str, tenant_id: Optional[str] = None) -> int:
        """Push values to the right of a list."""
        full_key = self._get_key(list_key, tenant_id)
        return await self._client.rpush(full_key, *values)
    
    async def lrange(self, list_key: str, start: int, stop: int,
                     tenant_id: Optional[str] = None) -> List[str]:
        """Get a range of values from a list."""
        full_key = self._get_key(list_key, tenant_id)
        return await self._client.lrange(full_key, start, stop)
    
    async def llen(self, list_key: str, tenant_id: Optional[str] = None) -> int:
        """Get the length of a list."""
        full_key = self._get_key(list_key, tenant_id)
        return await self._client.llen(full_key)
    
    # Set Operations
    async def sadd(self, set_key: str, *values: str, tenant_id: Optional[str] = None) -> int:
        """Add values to a set."""
        full_key = self._get_key(set_key, tenant_id)
        return await self._client.sadd(full_key, *values)
    
    async def srem(self, set_key: str, *values: str, tenant_id: Optional[str] = None) -> int:
        """Remove values from a set."""
        full_key = self._get_key(set_key, tenant_id)
        return await self._client.srem(full_key, *values)
    
    async def smembers(self, set_key: str, tenant_id: Optional[str] = None) -> Set[str]:
        """Get all members of a set."""
        full_key = self._get_key(set_key, tenant_id)
        return await self._client.smembers(full_key)
    
    async def sismember(self, set_key: str, value: str, tenant_id: Optional[str] = None) -> bool:
        """Check if a value is in a set."""
        full_key = self._get_key(set_key, tenant_id)
        return await self._client.sismember(full_key, value)
    
    # Sorted Set Operations
    async def zadd(self, zset_key: str, mapping: Dict[str, float],
                   tenant_id: Optional[str] = None) -> int:
        """Add members to a sorted set with scores."""
        full_key = self._get_key(zset_key, tenant_id)
        return await self._client.zadd(full_key, mapping)
    
    async def zrange(self, zset_key: str, start: int, stop: int,
                     withscores: bool = False, tenant_id: Optional[str] = None) -> List:
        """Get a range of members from a sorted set."""
        full_key = self._get_key(zset_key, tenant_id)
        return await self._client.zrange(full_key, start, stop, withscores=withscores)
    
    async def zrevrange(self, zset_key: str, start: int, stop: int,
                        withscores: bool = False, tenant_id: Optional[str] = None) -> List:
        """Get a reverse range of members from a sorted set."""
        full_key = self._get_key(zset_key, tenant_id)
        return await self._client.zrevrange(full_key, start, stop, withscores=withscores)
    
    # Caching Helpers
    async def cache_get_or_set(self, key: str, func: Callable, ttl: Optional[int] = None,
                              tenant_id: Optional[str] = None) -> Any:
        """Get from cache or compute and cache the result."""
        # Try to get from cache
        cached = await self.get_json(key, tenant_id)
        if cached is not None:
            return cached
        
        # Compute the value
        value = await func() if asyncio.iscoroutinefunction(func) else func()
        
        # Cache the result
        await self.set_json(key, value, tenant_id, ttl)
        
        return value
    
    # Session Management
    async def create_session(self, session_id: str, data: Dict[str, Any],
                           ttl: int = 3600, tenant_id: Optional[str] = None) -> bool:
        """Create a session with data."""
        session_key = f"session:{session_id}"
        return await self.set_json(session_key, data, tenant_id, ttl)
    
    async def get_session(self, session_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get session data."""
        session_key = f"session:{session_id}"
        return await self.get_json(session_key, tenant_id)
    
    async def update_session(self, session_id: str, data: Dict[str, Any],
                           tenant_id: Optional[str] = None) -> bool:
        """Update session data."""
        session_key = f"session:{session_id}"
        current = await self.get_session(session_id, tenant_id)
        if current:
            current.update(data)
            ttl = await self.ttl(session_key, tenant_id)
            return await self.set_json(session_key, current, tenant_id, ttl if ttl > 0 else 3600)
        return False
    
    async def delete_session(self, session_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete a session."""
        session_key = f"session:{session_id}"
        return await self.delete(session_key, tenant_id)
    
    # Rate Limiting
    async def check_rate_limit(self, identifier: str, limit: int, window: int,
                              tenant_id: Optional[str] = None) -> tuple[bool, int]:
        """Check if rate limit is exceeded. Returns (is_allowed, remaining_calls)."""
        key = f"ratelimit:{identifier}"
        full_key = self._get_key(key, tenant_id)
        
        # Use a simple sliding window algorithm
        current = await self._client.incr(full_key)
        
        if current == 1:
            # First request in the window
            await self._client.expire(full_key, window)
        
        if current > limit:
            ttl = await self._client.ttl(full_key)
            return False, 0
        
        return True, limit - current
    
    # Distributed Locking
    @asynccontextmanager
    async def lock(self, resource: str, timeout: int = 10, tenant_id: Optional[str] = None):
        """Acquire a distributed lock."""
        import uuid
        lock_id = str(uuid.uuid4())
        lock_key = f"lock:{resource}"
        full_key = self._get_key(lock_key, tenant_id)
        
        # Try to acquire lock
        acquired = await self._client.set(full_key, lock_id, nx=True, ex=timeout)
        
        if not acquired:
            raise Exception(f"Could not acquire lock for {resource}")
        
        try:
            yield
        finally:
            # Release lock only if we still own it
            current_value = await self._client.get(full_key)
            if current_value == lock_id:
                await self._client.delete(full_key)
    
    # Pub/Sub Operations
    async def publish(self, channel: str, message: str, tenant_id: Optional[str] = None) -> int:
        """Publish a message to a channel."""
        full_channel = self._get_key(channel, tenant_id)
        return await self._client.publish(full_channel, message)
    
    @asynccontextmanager
    async def subscribe(self, *channels: str, tenant_id: Optional[str] = None):
        """Subscribe to channels."""
        pubsub = self._client.pubsub()
        full_channels = [self._get_key(ch, tenant_id) for ch in channels]
        
        await pubsub.subscribe(*full_channels)
        
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(*full_channels)
            await pubsub.close()
    
    # Monitoring and Stats
    async def get_info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis server information."""
        info = await self._client.info(section)
        return info
    
    async def get_memory_usage(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get memory usage statistics for a tenant."""
        pattern = self._get_key("*", tenant_id)
        
        # Sample keys to estimate memory usage
        cursor = 0
        total_memory = 0
        key_count = 0
        
        while True:
            cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                try:
                    memory = await self._client.memory_usage(key)
                    total_memory += memory or 0
                    key_count += 1
                except:
                    pass
            
            if cursor == 0:
                break
        
        return {
            "total_memory_bytes": total_memory,
            "key_count": key_count,
            "avg_memory_per_key": total_memory / key_count if key_count > 0 else 0
        }
    
    async def flush_tenant(self, tenant_id: str) -> int:
        """Delete all keys for a specific tenant."""
        pattern = self._get_key("*", tenant_id)
        
        cursor = 0
        deleted_count = 0
        
        while True:
            cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
            
            if keys:
                deleted_count += await self._client.delete(*keys)
            
            if cursor == 0:
                break
        
        return deleted_count


# Import asyncio for async operations
import asyncio

# Global client instance
redis_client = RedisClient()