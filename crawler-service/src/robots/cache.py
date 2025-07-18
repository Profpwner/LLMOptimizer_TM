"""Caching system for robots.txt files"""

import asyncio
import json
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta

import redis.asyncio as redis
import structlog

from .parser import RobotsParser, RobotsRule

logger = structlog.get_logger(__name__)


class RobotsCache:
    """
    Cache for robots.txt data with TTL support.
    Stores parsed rules in Redis for distributed access.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        parser: RobotsParser,
        default_ttl: int = 86400,  # 24 hours
        min_ttl: int = 3600,       # 1 hour
        max_ttl: int = 604800,     # 7 days
        cache_prefix: str = "crawler:robots"
    ):
        self.redis = redis_client
        self.parser = parser
        self.default_ttl = default_ttl
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self.cache_prefix = cache_prefix
        
        # In-memory cache for frequent lookups
        self._memory_cache: Dict[str, Dict] = {}
        self._memory_cache_expiry: Dict[str, float] = {}
        
    def _get_cache_key(self, domain: str) -> str:
        """Get Redis cache key for domain"""
        return f"{self.cache_prefix}:{domain}"
        
    async def get_rules(
        self,
        domain: str,
        force_refresh: bool = False
    ) -> Optional[Dict[str, RobotsRule]]:
        """Get parsed robots rules for domain"""
        # Check memory cache first
        if not force_refresh and domain in self._memory_cache:
            if time.time() < self._memory_cache_expiry.get(domain, 0):
                logger.debug("Robots rules from memory cache", domain=domain)
                return self._deserialize_rules(self._memory_cache[domain])
                
        # Check Redis cache
        if not force_refresh:
            cached = await self._get_from_redis(domain)
            if cached:
                # Update memory cache
                self._memory_cache[domain] = cached
                self._memory_cache_expiry[domain] = time.time() + 300  # 5 min
                return self._deserialize_rules(cached)
                
        # Fetch and parse
        logger.info("Fetching robots.txt", domain=domain)
        rules = await self.parser.parse_from_url(domain)
        
        if rules:
            # Cache the results
            await self._save_to_cache(domain, rules)
            
        return rules
        
    async def _get_from_redis(self, domain: str) -> Optional[Dict]:
        """Get cached rules from Redis"""
        key = self._get_cache_key(domain)
        
        try:
            data = await self.redis.get(key)
            if data:
                cached = json.loads(data)
                logger.debug("Robots rules from Redis cache", domain=domain)
                return cached
                
        except Exception as e:
            logger.error(
                "Error reading from Redis cache",
                domain=domain,
                error=str(e)
            )
            
        return None
        
    async def _save_to_cache(
        self,
        domain: str,
        rules: Dict[str, RobotsRule],
        ttl: Optional[int] = None
    ):
        """Save rules to cache"""
        key = self._get_cache_key(domain)
        ttl = ttl or self.default_ttl
        
        # Ensure TTL is within bounds
        ttl = max(self.min_ttl, min(ttl, self.max_ttl))
        
        try:
            # Serialize rules
            serialized = self._serialize_rules(rules)
            
            # Save to Redis
            await self.redis.setex(
                key,
                ttl,
                json.dumps(serialized)
            )
            
            # Update memory cache
            self._memory_cache[domain] = serialized
            self._memory_cache_expiry[domain] = time.time() + min(ttl, 300)
            
            logger.info(
                "Robots rules cached",
                domain=domain,
                ttl=ttl,
                rules_count=len(rules)
            )
            
        except Exception as e:
            logger.error(
                "Error saving to cache",
                domain=domain,
                error=str(e)
            )
            
    def _serialize_rules(self, rules: Dict[str, RobotsRule]) -> Dict:
        """Serialize rules for storage"""
        serialized = {}
        
        for user_agent, rule in rules.items():
            serialized[user_agent] = {
                "user_agent": rule.user_agent,
                "allowed_paths": rule.allowed_paths,
                "disallowed_paths": rule.disallowed_paths,
                "crawl_delay": rule.crawl_delay,
                "request_rate": rule.request_rate,
                "sitemaps": rule.sitemaps
            }
            
        return serialized
        
    def _deserialize_rules(self, data: Dict) -> Dict[str, RobotsRule]:
        """Deserialize rules from storage"""
        rules = {}
        
        for user_agent, rule_data in data.items():
            rules[user_agent] = RobotsRule(
                user_agent=rule_data["user_agent"],
                allowed_paths=rule_data.get("allowed_paths", []),
                disallowed_paths=rule_data.get("disallowed_paths", []),
                crawl_delay=rule_data.get("crawl_delay"),
                request_rate=rule_data.get("request_rate"),
                sitemaps=rule_data.get("sitemaps", [])
            )
            
        return rules
        
    async def can_crawl(
        self,
        url: str,
        domain: str,
        user_agent: Optional[str] = None
    ) -> bool:
        """Check if URL can be crawled"""
        rules = await self.get_rules(domain)
        
        if not rules:
            # No rules means allow
            return True
            
        return self.parser.can_crawl(url, rules, user_agent)
        
    async def get_crawl_delay(
        self,
        domain: str,
        user_agent: Optional[str] = None
    ) -> Optional[float]:
        """Get crawl delay for domain"""
        rules = await self.get_rules(domain)
        
        if not rules:
            return None
            
        return self.parser.get_crawl_delay(rules, user_agent)
        
    async def get_sitemaps(self, domain: str) -> List[str]:
        """Get sitemap URLs for domain"""
        rules = await self.get_rules(domain)
        
        if not rules:
            return []
            
        return self.parser.get_sitemaps(rules)
        
    async def invalidate(self, domain: str):
        """Invalidate cache for domain"""
        # Remove from memory cache
        self._memory_cache.pop(domain, None)
        self._memory_cache_expiry.pop(domain, None)
        
        # Remove from Redis
        key = self._get_cache_key(domain)
        await self.redis.delete(key)
        
        logger.info("Robots cache invalidated", domain=domain)
        
    async def clear_memory_cache(self):
        """Clear in-memory cache"""
        self._memory_cache.clear()
        self._memory_cache_expiry.clear()
        logger.info("Memory cache cleared")
        
    async def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        # Count Redis keys
        pattern = f"{self.cache_prefix}:*"
        cursor = 0
        redis_count = 0
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            redis_count += len(keys)
            
            if cursor == 0:
                break
                
        return {
            "memory_cache_size": len(self._memory_cache),
            "redis_cache_size": redis_count,
            "memory_cache_domains": list(self._memory_cache.keys())
        }
        
    async def cleanup_expired_memory_cache(self):
        """Remove expired entries from memory cache"""
        now = time.time()
        expired = [
            domain for domain, expiry in self._memory_cache_expiry.items()
            if expiry < now
        ]
        
        for domain in expired:
            self._memory_cache.pop(domain, None)
            self._memory_cache_expiry.pop(domain, None)
            
        if expired:
            logger.debug(
                "Cleaned expired memory cache entries",
                count=len(expired)
            )