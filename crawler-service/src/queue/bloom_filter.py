"""Bloom Filter implementation for URL deduplication"""

import hashlib
import math
from typing import List, Optional
import pickle

import redis.asyncio as redis
from pybloom_live import BloomFilter
import structlog

logger = structlog.get_logger(__name__)


class URLBloomFilter:
    """
    Distributed Bloom Filter for efficient URL deduplication.
    Uses Redis for persistence and sharing across workers.
    """
    
    def __init__(
        self,
        capacity: int = 10_000_000,  # 10M URLs
        error_rate: float = 0.001,    # 0.1% false positive rate
        redis_key: str = "crawler:bloom_filter"
    ):
        self.capacity = capacity
        self.error_rate = error_rate
        self.redis_key = redis_key
        
        # Initialize bloom filter
        self.bloom = BloomFilter(
            capacity=capacity,
            error_rate=error_rate
        )
        
        self._item_count = 0
        
    def _hash_url(self, url: str) -> str:
        """Generate hash for URL"""
        return hashlib.sha256(url.encode()).hexdigest()
        
    async def add(self, url: str) -> bool:
        """Add URL to bloom filter"""
        url_hash = self._hash_url(url)
        
        # Check if already exists
        if url_hash in self.bloom:
            return False
            
        # Add to bloom filter
        self.bloom.add(url_hash)
        self._item_count += 1
        
        # Log if approaching capacity
        if self._item_count > self.capacity * 0.9:
            logger.warning(
                "Bloom filter approaching capacity",
                current_items=self._item_count,
                capacity=self.capacity
            )
            
        return True
        
    async def add_many(self, urls: List[str]) -> int:
        """Add multiple URLs to bloom filter"""
        added = 0
        for url in urls:
            if await self.add(url):
                added += 1
        return added
        
    async def contains(self, url: str) -> bool:
        """Check if URL might be in bloom filter"""
        url_hash = self._hash_url(url)
        return url_hash in self.bloom
        
    async def contains_many(self, urls: List[str]) -> List[bool]:
        """Check multiple URLs"""
        return [await self.contains(url) for url in urls]
        
    async def save_to_redis(self, redis_client: redis.Redis):
        """Save bloom filter state to Redis"""
        try:
            # Serialize bloom filter
            bloom_data = pickle.dumps(self.bloom)
            
            # Store in Redis with metadata
            await redis_client.hset(
                self.redis_key,
                mapping={
                    "data": bloom_data,
                    "capacity": str(self.capacity),
                    "error_rate": str(self.error_rate),
                    "item_count": str(self._item_count)
                }
            )
            
            logger.info(
                "Bloom filter saved to Redis",
                items=self._item_count,
                size_bytes=len(bloom_data)
            )
            
        except Exception as e:
            logger.error("Failed to save bloom filter", error=str(e))
            raise
            
    async def load_from_redis(self, redis_client: redis.Redis) -> bool:
        """Load bloom filter state from Redis"""
        try:
            # Get data from Redis
            data = await redis_client.hgetall(self.redis_key)
            
            if not data or b"data" not in data:
                logger.info("No bloom filter data found in Redis")
                return False
                
            # Deserialize bloom filter
            self.bloom = pickle.loads(data[b"data"])
            
            # Restore metadata
            self.capacity = int(data.get(b"capacity", self.capacity))
            self.error_rate = float(data.get(b"error_rate", self.error_rate))
            self._item_count = int(data.get(b"item_count", 0))
            
            logger.info(
                "Bloom filter loaded from Redis",
                items=self._item_count,
                capacity=self.capacity
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to load bloom filter", error=str(e))
            # Initialize new bloom filter on error
            self.bloom = BloomFilter(
                capacity=self.capacity,
                error_rate=self.error_rate
            )
            self._item_count = 0
            return False
            
    async def clear(self):
        """Clear the bloom filter"""
        self.bloom = BloomFilter(
            capacity=self.capacity,
            error_rate=self.error_rate
        )
        self._item_count = 0
        logger.info("Bloom filter cleared")
        
    def estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes"""
        # Bloom filter size calculation
        m = -self.capacity * math.log(self.error_rate) / (math.log(2) ** 2)
        return int(m / 8)  # Convert bits to bytes
        
    @property
    def fill_ratio(self) -> float:
        """Get current fill ratio"""
        return self._item_count / self.capacity if self.capacity > 0 else 0
        
    def get_stats(self) -> dict:
        """Get bloom filter statistics"""
        return {
            "capacity": self.capacity,
            "item_count": self._item_count,
            "error_rate": self.error_rate,
            "fill_ratio": self.fill_ratio,
            "estimated_memory_bytes": self.estimate_memory_usage()
        }