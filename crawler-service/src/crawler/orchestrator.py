"""Crawler orchestration and job management"""

import asyncio
import uuid
import hashlib
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
import json

import redis.asyncio as redis
from pydantic import BaseModel, HttpUrl
import structlog

from ..queue import URLQueueManager, QueuePriority, URLBloomFilter, DomainRateLimiter
from ..robots import RobotsCache, RobotsParser, SitemapParser
from .worker import WorkerPool
from .crawler import CrawlResult

logger = structlog.get_logger(__name__)


class CrawlJobStatus(str, Enum):
    """Crawl job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlJobConfig(BaseModel):
    """Configuration for a crawl job"""
    start_urls: List[HttpUrl]
    allowed_domains: Optional[List[str]] = None
    max_depth: int = 10
    max_pages: Optional[int] = None
    include_sitemaps: bool = True
    follow_robots: bool = True
    user_agent: Optional[str] = None
    rate_limit_rps: float = 1.0
    custom_headers: Dict[str, str] = {}
    include_patterns: List[str] = []
    exclude_patterns: List[str] = []
    
    
class CrawlJob(BaseModel):
    """Represents a crawl job"""
    job_id: str
    config: CrawlJobConfig
    status: CrawlJobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stats: Dict = {}
    error: Optional[str] = None
    
    
class CrawlOrchestrator:
    """
    Orchestrates crawling operations:
    - Job management
    - Progress tracking
    - Result aggregation
    - Worker coordination
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        worker_pool: Optional[WorkerPool] = None,
        result_handler: Optional[Callable[[str, CrawlResult], None]] = None,
        job_prefix: str = "crawler:job",
        result_prefix: str = "crawler:result"
    ):
        self.redis = redis_client
        self.worker_pool = worker_pool
        self.result_handler = result_handler
        self.job_prefix = job_prefix
        self.result_prefix = result_prefix
        
        # Component initialization
        self.queue_manager: Optional[URLQueueManager] = None
        self.robots_cache: Optional[RobotsCache] = None
        self.sitemap_parser: Optional[SitemapParser] = None
        
        # Active jobs tracking
        self._active_jobs: Dict[str, CrawlJob] = {}
        self._job_tasks: Dict[str, asyncio.Task] = {}
        
    async def initialize(self):
        """Initialize orchestrator components"""
        # Initialize queue manager
        bloom_filter = URLBloomFilter()
        rate_limiter = DomainRateLimiter(self.redis)
        
        self.queue_manager = URLQueueManager(
            redis_client=self.redis,
            bloom_filter=bloom_filter,
            rate_limiter=rate_limiter
        )
        await self.queue_manager.initialize()
        
        # Initialize robots cache
        parser = RobotsParser()
        self.robots_cache = RobotsCache(self.redis, parser)
        
        # Initialize sitemap parser
        self.sitemap_parser = SitemapParser()
        
        logger.info("Crawl orchestrator initialized")
        
    async def shutdown(self):
        """Shutdown orchestrator"""
        # Cancel all active jobs
        for job_id in list(self._job_tasks.keys()):
            await self.cancel_job(job_id)
            
        # Shutdown components
        if self.queue_manager:
            await self.queue_manager.shutdown()
            
        logger.info("Crawl orchestrator shut down")
        
    async def create_job(self, config: CrawlJobConfig) -> CrawlJob:
        """Create a new crawl job"""
        job_id = str(uuid.uuid4())
        
        job = CrawlJob(
            job_id=job_id,
            config=config,
            status=CrawlJobStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        # Save job to Redis
        await self._save_job(job)
        
        logger.info(
            "Crawl job created",
            job_id=job_id,
            start_urls=len(config.start_urls)
        )
        
        return job
        
    async def start_job(self, job_id: str) -> bool:
        """Start a crawl job"""
        job = await self.get_job(job_id)
        
        if not job:
            logger.error("Job not found", job_id=job_id)
            return False
            
        if job.status != CrawlJobStatus.PENDING:
            logger.warning(
                "Job not in pending state",
                job_id=job_id,
                status=job.status
            )
            return False
            
        # Update job status
        job.status = CrawlJobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self._save_job(job)
        
        # Start job task
        task = asyncio.create_task(self._run_job(job))
        self._job_tasks[job_id] = task
        self._active_jobs[job_id] = job
        
        logger.info("Crawl job started", job_id=job_id)
        return True
        
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        if job_id in self._job_tasks:
            task = self._job_tasks[job_id]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
                
            del self._job_tasks[job_id]
            
        job = await self.get_job(job_id)
        if job and job.status == CrawlJobStatus.RUNNING:
            job.status = CrawlJobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            await self._save_job(job)
            
            logger.info("Crawl job cancelled", job_id=job_id)
            return True
            
        return False
        
    async def get_job(self, job_id: str) -> Optional[CrawlJob]:
        """Get job by ID"""
        key = f"{self.job_prefix}:{job_id}"
        data = await self.redis.get(key)
        
        if data:
            return CrawlJob.parse_raw(data)
            
        return None
        
    async def list_jobs(
        self,
        status: Optional[CrawlJobStatus] = None,
        limit: int = 100
    ) -> List[CrawlJob]:
        """List crawl jobs"""
        pattern = f"{self.job_prefix}:*"
        jobs = []
        
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
                    job = CrawlJob.parse_raw(data)
                    if not status or job.status == status:
                        jobs.append(job)
                        
            if cursor == 0 or len(jobs) >= limit:
                break
                
        # Sort by created_at descending
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        return jobs[:limit]
        
    async def get_job_stats(self, job_id: str) -> Dict:
        """Get detailed job statistics"""
        job = await self.get_job(job_id)
        
        if not job:
            return {}
            
        # Get queue stats for job
        queue_stats = await self.queue_manager.get_stats()
        
        # Get crawled URLs count
        result_pattern = f"{self.result_prefix}:{job_id}:*"
        cursor = 0
        crawled_count = 0
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=result_pattern,
                count=100
            )
            crawled_count += len(keys)
            
            if cursor == 0:
                break
                
        stats = {
            "job_id": job_id,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "duration_seconds": None,
            "urls_crawled": crawled_count,
            "queue_stats": queue_stats,
            "config": job.config.dict()
        }
        
        if job.started_at:
            end_time = job.completed_at or datetime.utcnow()
            stats["duration_seconds"] = (end_time - job.started_at).total_seconds()
            
        return stats
        
    async def _run_job(self, job: CrawlJob):
        """Run a crawl job"""
        try:
            # Set up job-specific queue namespace
            original_prefix = self.queue_manager.queue_prefix
            self.queue_manager.queue_prefix = f"{original_prefix}:{job.job_id}"
            
            # Configure rate limiting
            for domain in job.config.allowed_domains or []:
                await self.queue_manager.rate_limiter.set_domain_config(
                    domain,
                    requests_per_second=job.config.rate_limit_rps
                )
                
            # Add start URLs
            for url in job.config.start_urls:
                await self.queue_manager.add_url(
                    str(url),
                    priority=QueuePriority.HIGH,
                    metadata={"job_id": job.job_id}
                )
                
            # Discover and add sitemap URLs
            if job.config.include_sitemaps:
                await self._process_sitemaps(job)
                
            # Monitor job progress
            await self._monitor_job_progress(job)
            
            # Mark job as completed
            job.status = CrawlJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
        except asyncio.CancelledError:
            job.status = CrawlJobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            raise
            
        except Exception as e:
            logger.error(
                "Job failed",
                job_id=job.job_id,
                error=str(e)
            )
            job.status = CrawlJobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            
        finally:
            # Restore original prefix
            self.queue_manager.queue_prefix = original_prefix
            
            # Save final job state
            await self._save_job(job)
            
            # Clean up
            if job.job_id in self._active_jobs:
                del self._active_jobs[job.job_id]
            if job.job_id in self._job_tasks:
                del self._job_tasks[job.job_id]
                
    async def _process_sitemaps(self, job: CrawlJob):
        """Process sitemaps for job"""
        sitemap_urls = []
        
        # Get sitemaps from robots.txt
        for start_url in job.config.start_urls:
            domain = urlparse(str(start_url)).netloc
            
            sitemaps = await self.robots_cache.get_sitemaps(domain)
            sitemap_urls.extend(sitemaps)
            
            # Discover additional sitemaps
            discovered = await self.sitemap_parser.discover_sitemaps(domain)
            sitemap_urls.extend(discovered)
            
        # Parse sitemaps and add URLs
        if sitemap_urls:
            entries = await self.sitemap_parser.parse_all_sitemaps(
                list(set(sitemap_urls))
            )
            
            for entry in entries:
                # Check if URL matches allowed domains
                if job.config.allowed_domains:
                    domain = urlparse(entry.loc).netloc
                    if domain not in job.config.allowed_domains:
                        continue
                        
                # Calculate priority based on sitemap data
                priority = QueuePriority.MEDIUM
                if entry.priority and entry.priority > 0.7:
                    priority = QueuePriority.HIGH
                elif entry.priority and entry.priority < 0.3:
                    priority = QueuePriority.LOW
                    
                await self.queue_manager.add_url(
                    entry.loc,
                    priority=priority,
                    metadata={
                        "job_id": job.job_id,
                        "from_sitemap": True
                    }
                )
                
            logger.info(
                "Sitemap URLs added",
                job_id=job.job_id,
                sitemap_count=len(sitemap_urls),
                url_count=len(entries)
            )
            
    async def _monitor_job_progress(self, job: CrawlJob):
        """Monitor job progress until completion"""
        check_interval = 5.0  # seconds
        no_progress_limit = 60  # seconds
        last_crawled_count = 0
        no_progress_time = 0
        
        while True:
            # Get current stats
            stats = await self.queue_manager.get_stats()
            
            # Check if we've hit max pages limit
            if job.config.max_pages:
                visited = stats.get("visited_size", 0)
                if visited >= job.config.max_pages:
                    logger.info(
                        "Max pages reached",
                        job_id=job.job_id,
                        pages=visited
                    )
                    break
                    
            # Check if all queues are empty
            total_queued = sum(
                stats.get(f"queue_{p.name.lower()}_size", 0)
                for p in QueuePriority
            )
            processing = stats.get("processing_size", 0)
            
            if total_queued == 0 and processing == 0:
                logger.info(
                    "All URLs processed",
                    job_id=job.job_id
                )
                break
                
            # Check for progress
            current_crawled = stats.get("visited_size", 0)
            if current_crawled > last_crawled_count:
                last_crawled_count = current_crawled
                no_progress_time = 0
            else:
                no_progress_time += check_interval
                
            # Stop if no progress for too long
            if no_progress_time >= no_progress_limit:
                logger.warning(
                    "No progress detected, stopping job",
                    job_id=job.job_id,
                    no_progress_seconds=no_progress_time
                )
                break
                
            # Update job stats
            job.stats = {
                "urls_crawled": current_crawled,
                "urls_queued": total_queued,
                "urls_processing": processing,
                "urls_failed": stats.get("failed_size", 0)
            }
            await self._save_job(job)
            
            # Wait before next check
            await asyncio.sleep(check_interval)
            
    async def _save_job(self, job: CrawlJob):
        """Save job to Redis"""
        key = f"{self.job_prefix}:{job.job_id}"
        await self.redis.setex(
            key,
            86400 * 7,  # 7 days TTL
            job.json()
        )
        
    async def get_job_results(
        self,
        job_id: str,
        offset: int = 0,
        limit: int = 100
    ) -> List[Dict]:
        """Get crawl results for a job"""
        pattern = f"{self.result_prefix}:{job_id}:*"
        results = []
        
        cursor = 0
        count = 0
        
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                if count >= offset and len(results) < limit:
                    data = await self.redis.get(key)
                    if data:
                        results.append(json.loads(data))
                count += 1
                
            if cursor == 0 or len(results) >= limit:
                break
                
        return results
        
    async def handle_crawl_result(self, job_id: str, result: CrawlResult):
        """Handle a crawl result"""
        # Save result to Redis
        url_hash = hashlib.sha256(result.url.encode()).hexdigest()[:16]
        key = f"{self.result_prefix}:{job_id}:{url_hash}"
        
        await self.redis.setex(
            key,
            86400 * 7,  # 7 days TTL
            json.dumps(result.to_dict())
        )
        
        # Call custom handler if provided
        if self.result_handler:
            await self.result_handler(job_id, result)