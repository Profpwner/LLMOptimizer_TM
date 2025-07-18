"""Domain-specific rate limiting for crawlers"""

import asyncio
import time
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

import redis.asyncio as redis
from aiolimiter import AsyncLimiter
import structlog
from urllib.parse import urlparse

logger = structlog.get_logger(__name__)


class DomainRateLimiter:
    """
    Rate limiter that respects crawl delays and manages per-domain limits.
    Supports both in-memory and Redis-based distributed rate limiting.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        default_requests_per_second: float = 1.0,
        default_burst_size: int = 5,
        redis_prefix: str = "crawler:ratelimit",
        respect_crawl_delay: bool = True
    ):
        self.redis = redis_client
        self.default_rps = default_requests_per_second
        self.default_burst = default_burst_size
        self.redis_prefix = redis_prefix
        self.respect_crawl_delay = respect_crawl_delay
        
        # In-memory rate limiters per domain
        self._limiters: Dict[str, AsyncLimiter] = {}
        
        # Domain-specific configurations
        self._domain_configs: Dict[str, Dict] = {}
        
        # Track last access times
        self._last_access: Dict[str, float] = {}
        
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc.lower()
        
    async def set_domain_config(
        self,
        domain: str,
        requests_per_second: Optional[float] = None,
        burst_size: Optional[int] = None,
        crawl_delay: Optional[float] = None
    ):
        """Set rate limit configuration for a specific domain"""
        config = {}
        
        if requests_per_second is not None:
            config["rps"] = requests_per_second
            
        if burst_size is not None:
            config["burst"] = burst_size
            
        if crawl_delay is not None and self.respect_crawl_delay:
            # Convert crawl delay to requests per second
            if crawl_delay > 0:
                config["rps"] = 1.0 / crawl_delay
                config["burst"] = 1
                
        self._domain_configs[domain] = config
        
        # Update Redis if available
        if self.redis:
            key = f"{self.redis_prefix}:config:{domain}"
            await self.redis.hset(
                key,
                mapping={k: str(v) for k, v in config.items()}
            )
            await self.redis.expire(key, 86400)  # 24 hour TTL
            
        # Remove existing limiter to force recreation
        if domain in self._limiters:
            del self._limiters[domain]
            
        logger.info(
            "Domain rate limit configured",
            domain=domain,
            config=config
        )
        
    async def get_domain_config(self, domain: str) -> Dict:
        """Get rate limit configuration for a domain"""
        # Check in-memory first
        if domain in self._domain_configs:
            return self._domain_configs[domain]
            
        # Check Redis if available
        if self.redis:
            key = f"{self.redis_prefix}:config:{domain}"
            config = await self.redis.hgetall(key)
            
            if config:
                # Convert Redis data to proper types
                parsed_config = {}
                if b"rps" in config:
                    parsed_config["rps"] = float(config[b"rps"])
                if b"burst" in config:
                    parsed_config["burst"] = int(config[b"burst"])
                    
                self._domain_configs[domain] = parsed_config
                return parsed_config
                
        # Return default config
        return {
            "rps": self.default_rps,
            "burst": self.default_burst
        }
        
    def _get_limiter(self, domain: str) -> AsyncLimiter:
        """Get or create rate limiter for domain"""
        if domain not in self._limiters:
            config = self._domain_configs.get(domain, {})
            rps = config.get("rps", self.default_rps)
            burst = config.get("burst", self.default_burst)
            
            self._limiters[domain] = AsyncLimiter(
                max_rate=rps,
                time_period=1.0,
                burst=burst
            )
            
        return self._limiters[domain]
        
    async def can_crawl(self, domain: str) -> bool:
        """Check if we can crawl this domain now"""
        if self.redis:
            return await self._can_crawl_distributed(domain)
        else:
            return await self._can_crawl_local(domain)
            
    async def _can_crawl_local(self, domain: str) -> bool:
        """Local in-memory rate limit check"""
        limiter = self._get_limiter(domain)
        
        # Check if limiter has capacity
        if limiter.has_capacity():
            # Check minimum delay between requests
            last_access = self._last_access.get(domain, 0)
            config = await self.get_domain_config(domain)
            min_delay = 1.0 / config.get("rps", self.default_rps)
            
            if time.time() - last_access >= min_delay:
                return True
                
        return False
        
    async def _can_crawl_distributed(self, domain: str) -> bool:
        """Distributed rate limit check using Redis"""
        config = await self.get_domain_config(domain)
        rps = config.get("rps", self.default_rps)
        burst = config.get("burst", self.default_burst)
        
        # Use Redis sorted set for sliding window rate limiting
        key = f"{self.redis_prefix}:window:{domain}"
        now = time.time()
        window_size = burst / rps  # Time window in seconds
        
        # Remove old entries outside the window
        await self.redis.zremrangebyscore(key, 0, now - window_size)
        
        # Count requests in current window
        count = await self.redis.zcard(key)
        
        # Check if under limit
        return count < burst
        
    async def record_access(self, domain: str):
        """Record that we accessed this domain"""
        now = time.time()
        self._last_access[domain] = now
        
        if self.redis:
            await self._record_access_distributed(domain, now)
        else:
            await self._record_access_local(domain)
            
    async def _record_access_local(self, domain: str):
        """Record access locally"""
        limiter = self._get_limiter(domain)
        async with limiter:
            pass  # Just acquire the rate limit slot
            
    async def _record_access_distributed(self, domain: str, timestamp: float):
        """Record access in Redis"""
        key = f"{self.redis_prefix}:window:{domain}"
        
        # Add timestamp to sorted set
        await self.redis.zadd(key, {str(timestamp): timestamp})
        
        # Set expiry on key
        config = await self.get_domain_config(domain)
        rps = config.get("rps", self.default_rps)
        burst = config.get("burst", self.default_burst)
        window_size = int(burst / rps) + 60  # Add buffer
        
        await self.redis.expire(key, window_size)
        
    async def wait_if_needed(self, domain: str) -> float:
        """Wait if necessary and return wait time"""
        start_time = time.time()
        
        while not await self.can_crawl(domain):
            await asyncio.sleep(0.1)
            
            # Timeout after 30 seconds
            if time.time() - start_time > 30:
                logger.warning(
                    "Rate limit wait timeout",
                    domain=domain,
                    wait_time=30
                )
                break
                
        wait_time = time.time() - start_time
        
        if wait_time > 0:
            logger.debug(
                "Rate limit wait completed",
                domain=domain,
                wait_time=wait_time
            )
            
        return wait_time
        
    async def get_stats(self) -> Dict[str, Dict]:
        """Get rate limiting statistics"""
        stats = {}
        
        # Get stats for each domain
        for domain in self._domain_configs:
            config = await self.get_domain_config(domain)
            
            domain_stats = {
                "config": config,
                "last_access": self._last_access.get(domain, 0)
            }
            
            if self.redis:
                # Get current window count
                key = f"{self.redis_prefix}:window:{domain}"
                count = await self.redis.zcard(key)
                domain_stats["current_window_count"] = count
                
            stats[domain] = domain_stats
            
        return stats
        
    async def clear_domain(self, domain: str):
        """Clear rate limit data for a domain"""
        # Clear in-memory data
        if domain in self._limiters:
            del self._limiters[domain]
        if domain in self._domain_configs:
            del self._domain_configs[domain]
        if domain in self._last_access:
            del self._last_access[domain]
            
        # Clear Redis data
        if self.redis:
            keys = [
                f"{self.redis_prefix}:config:{domain}",
                f"{self.redis_prefix}:window:{domain}"
            ]
            await self.redis.delete(*keys)
            
        logger.info("Domain rate limit data cleared", domain=domain)
        
    async def clear_all(self):
        """Clear all rate limit data"""
        self._limiters.clear()
        self._domain_configs.clear()
        self._last_access.clear()
        
        if self.redis:
            # Clear all rate limit keys
            pattern = f"{self.redis_prefix}:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await self.redis.delete(*keys)
                    
                if cursor == 0:
                    break
                    
        logger.warning("All rate limit data cleared")