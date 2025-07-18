"""Monitoring and metrics for crawler service"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge, Info
import structlog

logger = structlog.get_logger(__name__)

# Prometheus metrics
crawl_jobs_total = Counter(
    "crawler_jobs_total",
    "Total number of crawl jobs",
    ["status"]
)

crawl_urls_total = Counter(
    "crawler_urls_total",
    "Total URLs processed",
    ["status", "domain"]
)

crawl_duration_histogram = Histogram(
    "crawler_duration_seconds",
    "Crawl duration in seconds",
    ["domain"]
)

queue_size_gauge = Gauge(
    "crawler_queue_size",
    "Current queue size",
    ["priority"]
)

active_crawls_gauge = Gauge(
    "crawler_active_crawls",
    "Number of active crawls"
)

robots_cache_hits = Counter(
    "crawler_robots_cache_hits_total",
    "Robots.txt cache hits"
)

robots_cache_misses = Counter(
    "crawler_robots_cache_misses_total",
    "Robots.txt cache misses"
)

rate_limit_waits = Counter(
    "crawler_rate_limit_waits_total",
    "Number of rate limit waits",
    ["domain"]
)

crawler_info = Info(
    "crawler",
    "Crawler service information"
)


class CrawlerMonitor:
    """
    Monitors crawler operations and provides metrics.
    Tracks performance, errors, and system health.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        metrics_prefix: str = "crawler:metrics",
        update_interval: float = 10.0
    ):
        self.redis = redis_client
        self.metrics_prefix = metrics_prefix
        self.update_interval = update_interval
        
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Set crawler info
        crawler_info.info({
            "version": "1.0.0",
            "start_time": datetime.utcnow().isoformat()
        })
        
    async def start(self):
        """Start monitoring"""
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Crawler monitor started")
        
    async def stop(self):
        """Stop monitoring"""
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Crawler monitor stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                await self._update_metrics()
            except Exception as e:
                logger.error("Error updating metrics", error=str(e))
                
            await asyncio.sleep(self.update_interval)
            
    async def _update_metrics(self):
        """Update all metrics"""
        # Get queue sizes
        await self._update_queue_metrics()
        
        # Get job metrics
        await self._update_job_metrics()
        
        # Get performance metrics
        await self._update_performance_metrics()
        
    async def _update_queue_metrics(self):
        """Update queue-related metrics"""
        # Queue sizes by priority
        for priority in ["critical", "high", "medium", "low", "deferred"]:
            key = f"crawler:queue:{priority}"
            size = await self.redis.zcard(key)
            queue_size_gauge.labels(priority=priority).set(size)
            
        # Active crawls
        processing_key = "crawler:queue:processing"
        active = await self.redis.scard(processing_key)
        active_crawls_gauge.set(active)
        
    async def _update_job_metrics(self):
        """Update job-related metrics"""
        # Count jobs by status
        pattern = "crawler:job:*"
        status_counts = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    try:
                        job_data = json.loads(data)
                        status = job_data.get("status", "unknown")
                        if status in status_counts:
                            status_counts[status] += 1
                    except Exception:
                        pass
                        
            if cursor == 0:
                break
                
        # Update metrics
        for status, count in status_counts.items():
            crawl_jobs_total.labels(status=status)._value.set(count)
            
    async def _update_performance_metrics(self):
        """Update performance metrics"""
        # Get recent performance data
        perf_key = f"{self.metrics_prefix}:performance"
        perf_data = await self.redis.hgetall(perf_key)
        
        if perf_data:
            # Process performance data
            for metric, value in perf_data.items():
                metric_str = metric.decode() if isinstance(metric, bytes) else metric
                value_str = value.decode() if isinstance(value, bytes) else value
                
                try:
                    # Parse metric type and labels
                    parts = metric_str.split(":")
                    if len(parts) >= 2:
                        metric_type = parts[0]
                        
                        if metric_type == "crawl_duration":
                            domain = parts[1] if len(parts) > 1 else "unknown"
                            duration = float(value_str)
                            crawl_duration_histogram.labels(domain=domain).observe(duration)
                            
                except Exception as e:
                    logger.error(
                        "Error processing performance metric",
                        metric=metric_str,
                        error=str(e)
                    )
                    
    async def record_crawl(
        self,
        url: str,
        status: str,
        duration: float,
        domain: Optional[str] = None
    ):
        """Record a crawl event"""
        if not domain:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
        # Update counters
        crawl_urls_total.labels(status=status, domain=domain).inc()
        
        # Update histogram
        crawl_duration_histogram.labels(domain=domain).observe(duration)
        
        # Store in Redis for aggregation
        perf_key = f"{self.metrics_prefix}:performance"
        await self.redis.hset(
            perf_key,
            f"crawl_duration:{domain}",
            str(duration)
        )
        
        # Set expiry
        await self.redis.expire(perf_key, 3600)  # 1 hour
        
    async def record_rate_limit_wait(self, domain: str, wait_time: float):
        """Record rate limit wait event"""
        rate_limit_waits.labels(domain=domain).inc()
        
        # Store wait time
        key = f"{self.metrics_prefix}:rate_limits"
        await self.redis.hset(key, domain, str(wait_time))
        await self.redis.expire(key, 3600)
        
    async def record_robots_cache_hit(self, hit: bool):
        """Record robots.txt cache hit/miss"""
        if hit:
            robots_cache_hits.inc()
        else:
            robots_cache_misses.inc()
            
    async def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": {},
            "jobs": {},
            "performance": {},
            "cache": {}
        }
        
        # Queue stats
        for priority in ["critical", "high", "medium", "low", "deferred"]:
            key = f"crawler:queue:{priority}"
            stats["queues"][priority] = await self.redis.zcard(key)
            
        stats["queues"]["processing"] = await self.redis.scard("crawler:queue:processing")
        stats["queues"]["visited"] = await self.redis.scard("crawler:visited")
        stats["queues"]["failed"] = await self.redis.scard("crawler:failed")
        
        # Job stats
        pattern = "crawler:job:*"
        job_count = 0
        cursor = 0
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            job_count += len(keys)
            
            if cursor == 0:
                break
                
        stats["jobs"]["total"] = job_count
        
        # Performance stats
        perf_key = f"{self.metrics_prefix}:performance"
        perf_data = await self.redis.hgetall(perf_key)
        
        total_duration = 0
        domain_count = 0
        
        for metric, value in perf_data.items():
            metric_str = metric.decode() if isinstance(metric, bytes) else metric
            value_str = value.decode() if isinstance(value, bytes) else value
            
            if metric_str.startswith("crawl_duration:"):
                total_duration += float(value_str)
                domain_count += 1
                
        if domain_count > 0:
            stats["performance"]["avg_crawl_duration"] = total_duration / domain_count
        else:
            stats["performance"]["avg_crawl_duration"] = 0
            
        # Cache stats
        cache_total = robots_cache_hits._value.get() + robots_cache_misses._value.get()
        if cache_total > 0:
            stats["cache"]["hit_rate"] = robots_cache_hits._value.get() / cache_total
        else:
            stats["cache"]["hit_rate"] = 0
            
        return stats
        
    async def get_domain_stats(self, domain: str) -> Dict:
        """Get statistics for a specific domain"""
        stats = {
            "domain": domain,
            "urls_crawled": 0,
            "avg_crawl_time": 0,
            "rate_limit_waits": 0,
            "last_crawled": None
        }
        
        # Get crawled URLs for domain
        visited_key = "crawler:visited"
        all_visited = await self.redis.smembers(visited_key)
        
        domain_urls = [
            url for url in all_visited
            if domain in url.decode() if isinstance(url, bytes) else url
        ]
        stats["urls_crawled"] = len(domain_urls)
        
        # Get performance data
        perf_key = f"{self.metrics_prefix}:performance"
        duration = await self.redis.hget(perf_key, f"crawl_duration:{domain}")
        
        if duration:
            stats["avg_crawl_time"] = float(
                duration.decode() if isinstance(duration, bytes) else duration
            )
            
        # Get rate limit data
        rl_key = f"{self.metrics_prefix}:rate_limits"
        wait_time = await self.redis.hget(rl_key, domain)
        
        if wait_time:
            stats["rate_limit_waits"] = float(
                wait_time.decode() if isinstance(wait_time, bytes) else wait_time
            )
            
        return stats
        
    async def create_health_check(self) -> Dict:
        """Create health check response"""
        try:
            # Check Redis connection
            await self.redis.ping()
            redis_healthy = True
        except Exception:
            redis_healthy = False
            
        # Get queue stats
        stats = await self.get_system_stats()
        
        # Determine overall health
        healthy = (
            redis_healthy and
            stats["queues"].get("processing", 0) < 1000  # Not overloaded
        )
        
        return {
            "healthy": healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "redis": redis_healthy,
                "queues": stats["queues"]["processing"] < 1000
            },
            "stats": stats
        }