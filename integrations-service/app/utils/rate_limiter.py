"""Rate limiting utilities using Redis."""

import redis.asyncio as redis
from typing import Optional
import time


class RateLimiter:
    """Rate limiter using Redis."""
    
    def __init__(self, redis_url: str, prefix: str = "rate_limit"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.prefix = prefix
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int = 100,
        window: int = 3600,
    ) -> bool:
        """Check if rate limit is exceeded."""
        full_key = f"{self.prefix}:{key}"
        current_time = int(time.time())
        window_start = current_time - window
        
        # Remove old entries
        await self.redis_client.zremrangebyscore(full_key, 0, window_start)
        
        # Count requests in current window
        count = await self.redis_client.zcard(full_key)
        
        if count >= limit:
            return False
        
        # Add current request
        await self.redis_client.zadd(full_key, {str(current_time): current_time})
        await self.redis_client.expire(full_key, window)
        
        return True
    
    async def get_remaining_requests(
        self,
        key: str,
        limit: int = 100,
        window: int = 3600,
    ) -> int:
        """Get remaining requests in current window."""
        full_key = f"{self.prefix}:{key}"
        current_time = int(time.time())
        window_start = current_time - window
        
        # Remove old entries
        await self.redis_client.zremrangebyscore(full_key, 0, window_start)
        
        # Count requests in current window
        count = await self.redis_client.zcard(full_key)
        
        return max(0, limit - count)
    
    async def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit for a key."""
        full_key = f"{self.prefix}:{key}"
        await self.redis_client.delete(full_key)