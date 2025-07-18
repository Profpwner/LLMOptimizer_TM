"""Crawler worker implementation for distributed crawling"""

import asyncio
import signal
import os
from typing import Optional, Dict, List, Callable
from datetime import datetime
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import traceback

import redis.asyncio as redis
import structlog
from prometheus_client import Counter, Histogram, Gauge

from ..queue import URLQueueManager, QueuePriority, URLBloomFilter, DomainRateLimiter
from ..robots import RobotsCache, RobotsParser
from .crawler import WebCrawler, CrawlResult

logger = structlog.get_logger(__name__)

# Prometheus metrics
urls_crawled = Counter("crawler_urls_crawled_total", "Total URLs crawled")
crawl_errors = Counter("crawler_errors_total", "Total crawl errors", ["error_type"])
crawl_duration = Histogram("crawler_crawl_duration_seconds", "Crawl duration")
active_workers = Gauge("crawler_active_workers", "Number of active workers")


class CrawlerWorker:
    """
    Individual crawler worker that processes URLs from queue.
    Designed to run in separate processes for true parallelism.
    """
    
    def __init__(
        self,
        worker_id: str,
        redis_url: str,
        queue_manager: Optional[URLQueueManager] = None,
        robots_cache: Optional[RobotsCache] = None,
        crawler: Optional[WebCrawler] = None,
        result_callback: Optional[Callable[[CrawlResult], None]] = None,
        max_depth: int = 10
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.queue_manager = queue_manager
        self.robots_cache = robots_cache
        self.crawler = crawler
        self.result_callback = result_callback
        self.max_depth = max_depth
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._redis_client: Optional[redis.Redis] = None
        
    async def initialize(self):
        """Initialize worker components"""
        # Create Redis connection
        self._redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Initialize components if not provided
        if not self.queue_manager:
            bloom_filter = URLBloomFilter()
            rate_limiter = DomainRateLimiter(self._redis_client)
            
            self.queue_manager = URLQueueManager(
                redis_client=self._redis_client,
                bloom_filter=bloom_filter,
                rate_limiter=rate_limiter,
                max_depth=self.max_depth
            )
            await self.queue_manager.initialize()
            
        if not self.robots_cache:
            parser = RobotsParser()
            self.robots_cache = RobotsCache(
                redis_client=self._redis_client,
                parser=parser
            )
            
        if not self.crawler:
            self.crawler = WebCrawler()
            await self.crawler.start()
            
        active_workers.inc()
        logger.info("Crawler worker initialized", worker_id=self.worker_id)
        
    async def shutdown(self):
        """Shutdown worker gracefully"""
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        # Close components
        if self.queue_manager:
            await self.queue_manager.shutdown()
            
        if self.crawler:
            await self.crawler.close()
            
        if self._redis_client:
            await self._redis_client.close()
            
        active_workers.dec()
        logger.info("Crawler worker shut down", worker_id=self.worker_id)
        
    async def run(self, concurrent_crawls: int = 5):
        """Run worker main loop"""
        self._running = True
        
        try:
            # Start concurrent crawl tasks
            for i in range(concurrent_crawls):
                task = asyncio.create_task(
                    self._crawl_loop(f"{self.worker_id}-{i}")
                )
                self._tasks.append(task)
                
            # Wait for all tasks
            await asyncio.gather(*self._tasks)
            
        except asyncio.CancelledError:
            logger.info("Worker cancelled", worker_id=self.worker_id)
        except Exception as e:
            logger.error(
                "Worker error",
                worker_id=self.worker_id,
                error=str(e),
                traceback=traceback.format_exc()
            )
            
    async def _crawl_loop(self, task_id: str):
        """Main crawl loop for a task"""
        logger.info("Crawl task started", task_id=task_id)
        
        while self._running:
            try:
                # Get next URL from queue
                job = await self.queue_manager.get_url(timeout=5.0)
                
                if not job:
                    await asyncio.sleep(1)
                    continue
                    
                # Process the URL
                await self._process_url(job)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Crawl loop error",
                    task_id=task_id,
                    error=str(e),
                    traceback=traceback.format_exc()
                )
                await asyncio.sleep(1)
                
        logger.info("Crawl task stopped", task_id=task_id)
        
    async def _process_url(self, job):
        """Process a single crawl job"""
        url = str(job.url)
        domain = self.crawler.get_domain(url)
        
        try:
            # Check robots.txt
            if not await self.robots_cache.can_crawl(url, domain):
                logger.info("URL blocked by robots.txt", url=url)
                await self.queue_manager.mark_completed(job)
                return
                
            # Apply crawl delay from robots.txt
            crawl_delay = await self.robots_cache.get_crawl_delay(domain)
            if crawl_delay:
                await self.queue_manager.rate_limiter.set_domain_config(
                    domain,
                    crawl_delay=crawl_delay
                )
                
            # Wait for rate limit
            await self.queue_manager.rate_limiter.wait_if_needed(domain)
            
            # Crawl the URL
            with crawl_duration.time():
                result = await self.crawler.crawl(url)
                
            if result.error:
                crawl_errors.labels(error_type="crawl_error").inc()
                logger.warning(
                    "Crawl failed",
                    url=url,
                    error=result.error
                )
                await self.queue_manager.mark_failed(job, result.error)
            else:
                urls_crawled.inc()
                
                # Extract and queue new URLs
                if result.links and job.depth < self.max_depth:
                    await self._queue_discovered_urls(
                        result.links,
                        job.depth + 1,
                        url
                    )
                    
                # Process result
                if self.result_callback:
                    await self._handle_result(result)
                    
                # Mark as completed
                await self.queue_manager.mark_completed(job)
                
                logger.info(
                    "URL crawled successfully",
                    url=url,
                    status=result.status_code,
                    links_found=len(result.links),
                    depth=job.depth
                )
                
        except Exception as e:
            crawl_errors.labels(error_type="processing_error").inc()
            logger.error(
                "Error processing URL",
                url=url,
                error=str(e),
                traceback=traceback.format_exc()
            )
            await self.queue_manager.mark_failed(job, str(e))
            
    async def _queue_discovered_urls(
        self,
        urls: List[str],
        depth: int,
        referrer: str
    ):
        """Queue newly discovered URLs"""
        # Filter same-domain URLs
        same_domain_urls = self.crawler.filter_same_domain_links(
            urls,
            referrer
        )
        
        # Prepare URLs with priorities
        url_priorities = []
        
        for url in same_domain_urls[:100]:  # Limit per page
            # Assign priority based on URL characteristics
            priority = self._calculate_url_priority(url)
            url_priorities.append((url, priority))
            
        # Add to queue
        added = await self.queue_manager.add_urls(
            url_priorities,
            depth=depth,
            referrer=referrer
        )
        
        if added > 0:
            logger.debug(
                "Discovered URLs queued",
                referrer=referrer,
                total_found=len(urls),
                same_domain=len(same_domain_urls),
                queued=added
            )
            
    def _calculate_url_priority(self, url: str) -> QueuePriority:
        """Calculate priority for discovered URL"""
        url_lower = url.lower()
        
        # High priority patterns
        if any(pattern in url_lower for pattern in [
            "/index", "/home", "/products", "/services",
            "/about", "/contact", "/api/", "/docs/"
        ]):
            return QueuePriority.HIGH
            
        # Low priority patterns
        if any(pattern in url_lower for pattern in [
            "/tag/", "/category/", "/page/", "/author/",
            "?print=", "?mobile=", "#comment"
        ]):
            return QueuePriority.LOW
            
        return QueuePriority.MEDIUM
        
    async def _handle_result(self, result: CrawlResult):
        """Handle crawl result"""
        try:
            if self.result_callback:
                if asyncio.iscoroutinefunction(self.result_callback):
                    await self.result_callback(result)
                else:
                    self.result_callback(result)
        except Exception as e:
            logger.error(
                "Error in result callback",
                url=result.url,
                error=str(e)
            )


class WorkerPool:
    """
    Manages a pool of crawler workers across multiple processes.
    Provides load balancing and fault tolerance.
    """
    
    def __init__(
        self,
        redis_url: str,
        num_workers: int = None,
        concurrent_crawls_per_worker: int = 5,
        result_callback: Optional[Callable[[CrawlResult], None]] = None
    ):
        self.redis_url = redis_url
        self.num_workers = num_workers or mp.cpu_count()
        self.concurrent_crawls_per_worker = concurrent_crawls_per_worker
        self.result_callback = result_callback
        
        self._workers: List[mp.Process] = []
        self._running = False
        
    def start(self):
        """Start worker pool"""
        self._running = True
        
        for i in range(self.num_workers):
            worker_id = f"worker-{i}"
            process = mp.Process(
                target=self._run_worker,
                args=(worker_id,)
            )
            process.start()
            self._workers.append(process)
            
        logger.info(
            "Worker pool started",
            num_workers=self.num_workers
        )
        
    def stop(self):
        """Stop worker pool"""
        self._running = False
        
        # Terminate all workers
        for process in self._workers:
            if process.is_alive():
                process.terminate()
                
        # Wait for termination
        for process in self._workers:
            process.join(timeout=10)
            if process.is_alive():
                process.kill()
                process.join()
                
        self._workers.clear()
        logger.info("Worker pool stopped")
        
    def _run_worker(self, worker_id: str):
        """Run worker in separate process"""
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Create new event loop for process
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        
        try:
            loop.run_until_complete(
                self._worker_main(worker_id)
            )
        except KeyboardInterrupt:
            logger.info("Worker interrupted", worker_id=worker_id)
        finally:
            loop.close()
            
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        raise KeyboardInterrupt()
        
    async def _worker_main(self, worker_id: str):
        """Worker main coroutine"""
        worker = CrawlerWorker(
            worker_id=worker_id,
            redis_url=self.redis_url,
            result_callback=self.result_callback
        )
        
        try:
            await worker.initialize()
            await worker.run(self.concurrent_crawls_per_worker)
        finally:
            await worker.shutdown()
            
    def get_status(self) -> Dict:
        """Get worker pool status"""
        alive_workers = sum(1 for p in self._workers if p.is_alive())
        
        return {
            "total_workers": self.num_workers,
            "alive_workers": alive_workers,
            "dead_workers": self.num_workers - alive_workers,
            "worker_pids": [p.pid for p in self._workers if p.is_alive()]
        }