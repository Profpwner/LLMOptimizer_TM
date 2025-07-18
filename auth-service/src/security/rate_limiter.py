"""Rate limiting service for API protection."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import asyncio
from collections import defaultdict

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException, status
import redis.asyncio as redis

from ..config import settings


class RateLimiter:
    """Advanced rate limiting with multiple strategies."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.local_cache = defaultdict(lambda: defaultdict(list))
        
        # Rate limit configurations
        self.limits = {
            'login': {
                'per_minute': 5,
                'per_hour': 20,
                'per_day': 100
            },
            'register': {
                'per_minute': 2,
                'per_hour': 10,
                'per_day': 20
            },
            'password_reset': {
                'per_minute': 2,
                'per_hour': 5,
                'per_day': 10
            },
            'api': {
                'per_minute': settings.RATE_LIMIT_PER_MINUTE,
                'per_hour': settings.RATE_LIMIT_PER_HOUR,
                'per_day': settings.RATE_LIMIT_PER_HOUR * 24
            },
            'mfa': {
                'per_minute': 10,
                'per_hour': 30,
                'per_day': 100
            }
        }
        
        # Create slowapi limiter for basic rate limiting
        self.limiter = Limiter(key_func=get_remote_address)
    
    async def check_rate_limit(
        self,
        key: str,
        limit_type: str = 'api',
        identifier: Optional[str] = None
    ) -> Tuple[bool, Dict[str, any]]:
        """Check if request is within rate limits."""
        if identifier is None:
            identifier = key
        
        limits = self.limits.get(limit_type, self.limits['api'])
        now = datetime.utcnow()
        
        # Check all time windows
        for window, limit in limits.items():
            window_start = self._get_window_start(now, window)
            
            if self.redis_client:
                count = await self._get_redis_count(identifier, limit_type, window)
            else:
                count = self._get_local_count(identifier, limit_type, window_start)
            
            if count >= limit:
                return False, {
                    'exceeded': True,
                    'window': window,
                    'limit': limit,
                    'current': count,
                    'retry_after': self._get_retry_after(window)
                }
        
        # Increment counters
        if self.redis_client:
            await self._increment_redis_count(identifier, limit_type)
        else:
            self._increment_local_count(identifier, limit_type, now)
        
        return True, {
            'exceeded': False,
            'remaining': self._get_remaining_limits(identifier, limit_type, limits)
        }
    
    async def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is temporarily blocked."""
        if self.redis_client:
            blocked = await self.redis_client.get(f"blocked_ip:{ip_address}")
            return blocked is not None
        else:
            # Simple in-memory check
            return ip_address in self.local_cache.get('blocked_ips', {})
    
    async def block_ip(self, ip_address: str, duration_minutes: int = 30, reason: str = ""):
        """Temporarily block an IP address."""
        if self.redis_client:
            await self.redis_client.setex(
                f"blocked_ip:{ip_address}",
                duration_minutes * 60,
                reason
            )
        else:
            self.local_cache['blocked_ips'][ip_address] = {
                'until': datetime.utcnow() + timedelta(minutes=duration_minutes),
                'reason': reason
            }
    
    async def add_to_blacklist(self, identifier: str, identifier_type: str = "ip"):
        """Add identifier to permanent blacklist."""
        if self.redis_client:
            await self.redis_client.sadd(f"blacklist:{identifier_type}", identifier)
        else:
            if 'blacklist' not in self.local_cache:
                self.local_cache['blacklist'] = defaultdict(set)
            self.local_cache['blacklist'][identifier_type].add(identifier)
    
    async def is_blacklisted(self, identifier: str, identifier_type: str = "ip") -> bool:
        """Check if identifier is blacklisted."""
        if self.redis_client:
            return await self.redis_client.sismember(f"blacklist:{identifier_type}", identifier)
        else:
            return identifier in self.local_cache.get('blacklist', {}).get(identifier_type, set())
    
    async def get_rate_limit_status(self, identifier: str, limit_type: str = 'api') -> Dict[str, any]:
        """Get current rate limit status for identifier."""
        limits = self.limits.get(limit_type, self.limits['api'])
        status = {}
        
        for window, limit in limits.items():
            if self.redis_client:
                count = await self._get_redis_count(identifier, limit_type, window)
            else:
                window_start = self._get_window_start(datetime.utcnow(), window)
                count = self._get_local_count(identifier, limit_type, window_start)
            
            status[window] = {
                'limit': limit,
                'current': count,
                'remaining': max(0, limit - count),
                'reset_at': self._get_window_reset_time(window)
            }
        
        return status
    
    def _get_window_start(self, now: datetime, window: str) -> datetime:
        """Get the start time for a rate limit window."""
        if window == 'per_minute':
            return now.replace(second=0, microsecond=0)
        elif window == 'per_hour':
            return now.replace(minute=0, second=0, microsecond=0)
        elif window == 'per_day':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return now
    
    def _get_retry_after(self, window: str) -> int:
        """Get seconds until rate limit window resets."""
        now = datetime.utcnow()
        
        if window == 'per_minute':
            reset_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        elif window == 'per_hour':
            reset_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        elif window == 'per_day':
            reset_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            reset_time = now + timedelta(minutes=1)
        
        return int((reset_time - now).total_seconds())
    
    def _get_window_reset_time(self, window: str) -> datetime:
        """Get the reset time for a rate limit window."""
        now = datetime.utcnow()
        
        if window == 'per_minute':
            return (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        elif window == 'per_hour':
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        elif window == 'per_day':
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return now + timedelta(minutes=1)
    
    async def _get_redis_count(self, identifier: str, limit_type: str, window: str) -> int:
        """Get count from Redis."""
        key = f"rate_limit:{limit_type}:{window}:{identifier}"
        count = await self.redis_client.get(key)
        return int(count) if count else 0
    
    async def _increment_redis_count(self, identifier: str, limit_type: str):
        """Increment count in Redis."""
        pipeline = self.redis_client.pipeline()
        
        for window in ['per_minute', 'per_hour', 'per_day']:
            key = f"rate_limit:{limit_type}:{window}:{identifier}"
            ttl = self._get_window_ttl(window)
            
            pipeline.incr(key)
            pipeline.expire(key, ttl)
        
        await pipeline.execute()
    
    def _get_window_ttl(self, window: str) -> int:
        """Get TTL in seconds for a window."""
        if window == 'per_minute':
            return 60
        elif window == 'per_hour':
            return 3600
        elif window == 'per_day':
            return 86400
        else:
            return 3600
    
    def _get_local_count(self, identifier: str, limit_type: str, window_start: datetime) -> int:
        """Get count from local cache."""
        entries = self.local_cache[limit_type].get(identifier, [])
        # Filter entries within the window
        valid_entries = [e for e in entries if e >= window_start]
        self.local_cache[limit_type][identifier] = valid_entries
        return len(valid_entries)
    
    def _increment_local_count(self, identifier: str, limit_type: str, timestamp: datetime):
        """Increment count in local cache."""
        self.local_cache[limit_type][identifier].append(timestamp)
        
        # Clean old entries
        cutoff = timestamp - timedelta(days=1)
        self.local_cache[limit_type][identifier] = [
            t for t in self.local_cache[limit_type][identifier] if t > cutoff
        ]
    
    def _get_remaining_limits(self, identifier: str, limit_type: str, limits: Dict[str, int]) -> Dict[str, int]:
        """Get remaining requests for each window."""
        remaining = {}
        now = datetime.utcnow()
        
        for window, limit in limits.items():
            window_start = self._get_window_start(now, window)
            count = self._get_local_count(identifier, limit_type, window_start)
            remaining[window] = max(0, limit - count)
        
        return remaining
    
    @staticmethod
    def create_rate_limit_exceeded_response() -> HTTPException:
        """Create a rate limit exceeded response."""
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": "60"}
        )