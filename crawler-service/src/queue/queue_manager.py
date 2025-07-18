"""Priority-based URL Queue Manager with Redis backend"""

import asyncio
import json
import time
from enum import IntEnum
from typing import Optional, List, Dict, Set, Tuple
from datetime import datetime, timedelta
import hashlib
from urllib.parse import urlparse

import redis.asyncio as redis
from pydantic import BaseModel, HttpUrl
import structlog
from yarl import URL

from .bloom_filter import URLBloomFilter
from .rate_limiter import DomainRateLimiter

logger = structlog.get_logger(__name__)


class QueuePriority(IntEnum):
    """URL crawl priority levels"""
    CRITICAL = 0  # Sitemap URLs, important pages
    HIGH = 1      # Internal links, high-value content
    MEDIUM = 2    # Regular pages
    LOW = 3       # External links, low-priority content
    DEFERRED = 4  # Rate-limited or problematic URLs


class CrawlJob(BaseModel):
    """Represents a URL to be crawled"""
    url: HttpUrl
    priority: QueuePriority = QueuePriority.MEDIUM
    depth: int = 0
    referrer: Optional[HttpUrl] = None
    discovered_at: datetime = datetime.utcnow()
    retry_count: int = 0
    metadata: Dict = {}
    
    class Config:
        use_enum_values = True


class URLQueueManager:
    """Manages URL queues with priority, deduplication, and persistence"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        bloom_filter: URLBloomFilter,
        rate_limiter: DomainRateLimiter,
        max_depth: int = 10,
        max_retries: int = 3,
        queue_prefix: str = "crawler:queue",
        visited_prefix: str = "crawler:visited",
        failed_prefix: str = "crawler:failed"
    ):
        self.redis = redis_client
        self.bloom_filter = bloom_filter
        self.rate_limiter = rate_limiter
        self.max_depth = max_depth
        self.max_retries = max_retries
        
        # Redis key prefixes
        self.queue_prefix = queue_prefix
        self.visited_prefix = visited_prefix
        self.failed_prefix = failed_prefix
        self.processing_set = f"{queue_prefix}:processing"
        self.stats_key = f"{queue_prefix}:stats"
        
        self._shutdown = False
        self._recovery_task = None
        
    async def initialize(self):
        """Initialize queue manager and start recovery task"""
        # Load bloom filter from Redis if exists
        await self.bloom_filter.load_from_redis(self.redis)
        
        # Start recovery task for stale processing items
        self._recovery_task = asyncio.create_task(self._recovery_loop())
        
        logger.info("URL queue manager initialized")
        
    async def shutdown(self):
        """Gracefully shutdown queue manager"""
        self._shutdown = True
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
                
        # Save bloom filter state
        await self.bloom_filter.save_to_redis(self.redis)
        logger.info("URL queue manager shut down")
        
    def _get_queue_key(self, priority: QueuePriority) -> str:
        """Get Redis key for priority queue"""
        return f"{self.queue_prefix}:{priority.name.lower()}"
        
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication"""
        parsed = URL(str(url))
        # Remove fragment, sort query params, lowercase host
        normalized = parsed.with_fragment(None)
        if normalized.query_string:
            # Sort query parameters for consistent hashing
            params = sorted(normalized.query.items())
            normalized = normalized.with_query(params)
        return str(normalized).lower()
        
    async def add_url(
        self,
        url: str,
        priority: QueuePriority = QueuePriority.MEDIUM,
        depth: int = 0,
        referrer: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Add URL to queue if not already seen"""
        # Normalize URL
        normalized_url = self._normalize_url(url)
        
        # Check depth limit
        if depth > self.max_depth:
            logger.debug(f"URL depth {depth} exceeds limit", url=url)
            return False
            
        # Check if already seen using bloom filter
        if await self.bloom_filter.contains(normalized_url):
            logger.debug("URL already seen", url=url)
            return False
            
        # Check if already visited in Redis
        if await self.redis.sismember(self.visited_prefix, normalized_url):
            logger.debug("URL already visited", url=url)
            return False
            
        # Create crawl job
        job = CrawlJob(
            url=normalized_url,
            priority=priority,
            depth=depth,
            referrer=referrer,
            metadata=metadata or {}
        )
        
        # Add to bloom filter
        await self.bloom_filter.add(normalized_url)
        
        # Add to priority queue
        queue_key = self._get_queue_key(priority)
        score = time.time()  # Use timestamp as score for FIFO within priority
        
        await self.redis.zadd(
            queue_key,
            {job.json(): score}
        )
        
        # Update stats
        await self._increment_stat("urls_added")
        
        logger.info(
            "URL added to queue",
            url=url,
            priority=priority.name,
            depth=depth
        )
        return True
        
    async def add_urls(
        self,
        urls: List[Tuple[str, QueuePriority]],
        depth: int = 0,
        referrer: Optional[str] = None
    ) -> int:
        """Batch add multiple URLs"""
        added = 0
        for url, priority in urls:
            if await self.add_url(url, priority, depth, referrer):
                added += 1
        return added
        
    async def get_url(self, timeout: float = 1.0) -> Optional[CrawlJob]:
        """Get next URL to crawl based on priority and rate limits"""
        start_time = time.time()
        
        while not self._shutdown and (time.time() - start_time) < timeout:
            # Try each priority queue in order
            for priority in QueuePriority:
                queue_key = self._get_queue_key(priority)
                
                # Get URLs from queue
                items = await self.redis.zrange(queue_key, 0, 9, withscores=True)
                
                for item_data, score in items:
                    try:
                        job = CrawlJob.parse_raw(item_data)
                        domain = urlparse(str(job.url)).netloc
                        
                        # Check rate limit
                        if await self.rate_limiter.can_crawl(domain):
                            # Remove from queue
                            removed = await self.redis.zrem(queue_key, item_data)
                            if removed:
                                # Add to processing set
                                await self.redis.sadd(self.processing_set, item_data)
                                
                                # Record domain access
                                await self.rate_limiter.record_access(domain)
                                
                                # Update stats
                                await self._increment_stat("urls_dequeued")
                                
                                logger.debug(
                                    "URL dequeued",
                                    url=str(job.url),
                                    priority=priority.name
                                )
                                return job
                        else:
                            # Move to deferred queue if rate limited
                            if priority != QueuePriority.DEFERRED:
                                await self._defer_url(job)
                                await self.redis.zrem(queue_key, item_data)
                                
                    except Exception as e:
                        logger.error("Error processing queue item", error=str(e))
                        await self.redis.zrem(queue_key, item_data)
                        
            # Brief sleep before retry
            await asyncio.sleep(0.1)
            
        return None
        
    async def mark_completed(self, job: CrawlJob):
        """Mark URL as successfully crawled"""
        job_data = job.json()
        
        # Remove from processing set
        await self.redis.srem(self.processing_set, job_data)
        
        # Add to visited set
        normalized_url = self._normalize_url(str(job.url))
        await self.redis.sadd(self.visited_prefix, normalized_url)
        
        # Store completion info
        completion_data = {
            "url": str(job.url),
            "completed_at": datetime.utcnow().isoformat(),
            "depth": job.depth,
            "retry_count": job.retry_count
        }
        
        await self.redis.hset(
            f"{self.visited_prefix}:info",
            normalized_url,
            json.dumps(completion_data)
        )
        
        # Update stats
        await self._increment_stat("urls_completed")
        
        logger.info("URL marked as completed", url=str(job.url))
        
    async def mark_failed(self, job: CrawlJob, error: str):
        """Mark URL as failed and potentially retry"""
        job_data = job.json()
        
        # Remove from processing set
        await self.redis.srem(self.processing_set, job_data)
        
        # Check retry limit
        if job.retry_count < self.max_retries:
            # Increment retry count and re-queue
            job.retry_count += 1
            job.priority = QueuePriority.LOW  # Lower priority for retries
            
            queue_key = self._get_queue_key(job.priority)
            score = time.time() + (60 * job.retry_count)  # Delay retries
            
            await self.redis.zadd(queue_key, {job.json(): score})
            
            logger.warning(
                "URL failed, retrying",
                url=str(job.url),
                retry_count=job.retry_count,
                error=error
            )
        else:
            # Add to failed set
            normalized_url = self._normalize_url(str(job.url))
            await self.redis.sadd(self.failed_prefix, normalized_url)
            
            # Store failure info
            failure_data = {
                "url": str(job.url),
                "failed_at": datetime.utcnow().isoformat(),
                "error": error,
                "retry_count": job.retry_count
            }
            
            await self.redis.hset(
                f"{self.failed_prefix}:info",
                normalized_url,
                json.dumps(failure_data)
            )
            
            # Update stats
            await self._increment_stat("urls_failed")
            
            logger.error(
                "URL permanently failed",
                url=str(job.url),
                error=error
            )
            
    async def _defer_url(self, job: CrawlJob):
        """Move URL to deferred queue"""
        job.priority = QueuePriority.DEFERRED
        queue_key = self._get_queue_key(QueuePriority.DEFERRED)
        score = time.time() + 300  # Defer for 5 minutes
        
        await self.redis.zadd(queue_key, {job.json(): score})
        logger.debug("URL deferred due to rate limit", url=str(job.url))
        
    async def _recovery_loop(self):
        """Recover stale items from processing set"""
        while not self._shutdown:
            try:
                # Get all items in processing set
                processing_items = await self.redis.smembers(self.processing_set)
                
                for item_data in processing_items:
                    try:
                        job = CrawlJob.parse_raw(item_data)
                        
                        # Check if item is stale (> 5 minutes)
                        age = datetime.utcnow() - job.discovered_at
                        if age > timedelta(minutes=5):
                            # Re-queue the item
                            await self.redis.srem(self.processing_set, item_data)
                            
                            queue_key = self._get_queue_key(job.priority)
                            await self.redis.zadd(
                                queue_key,
                                {item_data: time.time()}
                            )
                            
                            logger.warning(
                                "Recovered stale processing item",
                                url=str(job.url)
                            )
                            
                    except Exception as e:
                        logger.error(
                            "Error recovering item",
                            error=str(e)
                        )
                        await self.redis.srem(self.processing_set, item_data)
                        
            except Exception as e:
                logger.error("Error in recovery loop", error=str(e))
                
            # Run recovery every 60 seconds
            await asyncio.sleep(60)
            
    async def _increment_stat(self, stat_name: str):
        """Increment a statistics counter"""
        await self.redis.hincrby(self.stats_key, stat_name, 1)
        
    async def get_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        stats = await self.redis.hgetall(self.stats_key)
        
        # Get queue sizes
        for priority in QueuePriority:
            queue_key = self._get_queue_key(priority)
            size = await self.redis.zcard(queue_key)
            stats[f"queue_{priority.name.lower()}_size"] = size
            
        # Get other set sizes
        stats["processing_size"] = await self.redis.scard(self.processing_set)
        stats["visited_size"] = await self.redis.scard(self.visited_prefix)
        stats["failed_size"] = await self.redis.scard(self.failed_prefix)
        
        return {k.decode() if isinstance(k, bytes) else k: 
                int(v.decode() if isinstance(v, bytes) else v) 
                for k, v in stats.items()}
                
    async def clear_all(self):
        """Clear all queues and sets (for testing/reset)"""
        keys_to_delete = []
        
        # Queue keys
        for priority in QueuePriority:
            keys_to_delete.append(self._get_queue_key(priority))
            
        # Other keys
        keys_to_delete.extend([
            self.processing_set,
            self.visited_prefix,
            self.failed_prefix,
            f"{self.visited_prefix}:info",
            f"{self.failed_prefix}:info",
            self.stats_key
        ])
        
        if keys_to_delete:
            await self.redis.delete(*keys_to_delete)
            
        # Clear bloom filter
        await self.bloom_filter.clear()
        
        logger.warning("All queue data cleared")