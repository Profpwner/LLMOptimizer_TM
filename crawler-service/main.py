"""Crawler Service - FastAPI Application"""

import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import structlog
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, HttpUrl

from src.queue import URLQueueManager, URLBloomFilter, DomainRateLimiter
from src.robots import RobotsCache, RobotsParser
from src.crawler import CrawlOrchestrator, CrawlJobConfig, CrawlJobStatus, WorkerPool
from src.crawler.monitor import CrawlerMonitor
from src.crawler.enhanced_crawler import EnhancedWebCrawler, DuplicationPolicy
from src.rendering import BrowserPool

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global instances
redis_client: Optional[redis.Redis] = None
orchestrator: Optional[CrawlOrchestrator] = None
monitor: Optional[CrawlerMonitor] = None
worker_pool: Optional[WorkerPool] = None
enhanced_crawler: Optional[EnhancedWebCrawler] = None
browser_pool: Optional[BrowserPool] = None


class CrawlJobRequest(BaseModel):
    """Request model for creating a crawl job"""
    start_urls: List[HttpUrl]
    allowed_domains: Optional[List[str]] = None
    max_depth: int = 10
    max_pages: Optional[int] = None
    include_sitemaps: bool = True
    follow_robots: bool = True
    rate_limit_rps: float = 1.0
    

class CrawlJobResponse(BaseModel):
    """Response model for crawl job"""
    job_id: str
    status: str
    created_at: str
    stats: Dict = {}
    

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global redis_client, orchestrator, monitor, worker_pool, enhanced_crawler, browser_pool
    
    # Startup
    logger.info("Starting crawler service")
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = await redis.from_url(redis_url, decode_responses=True)
    
    # Initialize monitor
    monitor = CrawlerMonitor(redis_client)
    await monitor.start()
    
    # Initialize worker pool (if enabled)
    enable_workers = os.getenv("ENABLE_WORKERS", "true").lower() == "true"
    if enable_workers:
        num_workers = int(os.getenv("NUM_WORKERS", "4"))
        worker_pool = WorkerPool(
            redis_url=redis_url,
            num_workers=num_workers
        )
        worker_pool.start()
    
    # Initialize orchestrator
    orchestrator = CrawlOrchestrator(
        redis_client=redis_client,
        worker_pool=worker_pool
    )
    await orchestrator.initialize()
    
    # Initialize enhanced crawler (if enabled)
    enable_enhanced = os.getenv("ENABLE_ENHANCED_CRAWLER", "true").lower() == "true"
    if enable_enhanced:
        enable_js = os.getenv("ENABLE_JS_RENDERING", "true").lower() == "true"
        browser_pool_size = int(os.getenv("BROWSER_POOL_SIZE", "3"))
        
        # Initialize browser pool if JS rendering is enabled
        if enable_js:
            browser_pool = BrowserPool(max_browsers=browser_pool_size)
            await browser_pool.start()
        
        # Initialize enhanced crawler
        enhanced_crawler = EnhancedWebCrawler(
            redis_client=redis_client,
            enable_javascript=enable_js,
            enable_deduplication=True,
            enable_content_analysis=True,
            enable_structured_extraction=True,
            browser_pool_size=browser_pool_size
        )
        await enhanced_crawler.start()
    
    logger.info("Crawler service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down crawler service")
    
    if enhanced_crawler:
        await enhanced_crawler.close()
    
    if browser_pool:
        await browser_pool.stop()
    
    if monitor:
        await monitor.stop()
        
    if orchestrator:
        await orchestrator.shutdown()
        
    if worker_pool:
        worker_pool.stop()
        
    if redis_client:
        await redis_client.close()
        
    logger.info("Crawler service shut down")


app = FastAPI(
    title="Crawler Service",
    description="Intelligent website crawler with distributed architecture",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if monitor:
        health = await monitor.create_health_check()
        status_code = 200 if health["healthy"] else 503
        return JSONResponse(content=health, status_code=status_code)
    
    return JSONResponse(
        content={"healthy": False, "error": "Service not initialized"},
        status_code=503
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    metrics_data = generate_latest()
    return JSONResponse(
        content=metrics_data.decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/crawl", response_model=CrawlJobResponse)
async def create_crawl_job(
    request: CrawlJobRequest,
    background_tasks: BackgroundTasks
):
    """Create a new crawl job"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Create job config
    config = CrawlJobConfig(
        start_urls=request.start_urls,
        allowed_domains=request.allowed_domains,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
        include_sitemaps=request.include_sitemaps,
        follow_robots=request.follow_robots,
        rate_limit_rps=request.rate_limit_rps
    )
    
    # Create job
    job = await orchestrator.create_job(config)
    
    # Start job in background
    background_tasks.add_task(orchestrator.start_job, job.job_id)
    
    return CrawlJobResponse(
        job_id=job.job_id,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        stats=job.stats
    )


@app.get("/crawl/{job_id}")
async def get_crawl_job(job_id: str):
    """Get crawl job details"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    job = await orchestrator.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    stats = await orchestrator.get_job_stats(job_id)
    
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "config": job.config.dict(),
        "stats": stats,
        "error": job.error
    }


@app.post("/crawl/{job_id}/cancel")
async def cancel_crawl_job(job_id: str):
    """Cancel a running crawl job"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    success = await orchestrator.cancel_job(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or not running")
    
    return {"message": "Job cancelled successfully"}


@app.get("/crawl/{job_id}/results")
async def get_crawl_results(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get crawl results for a job"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    job = await orchestrator.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    results = await orchestrator.get_job_results(job_id, offset, limit)
    
    return {
        "job_id": job_id,
        "offset": offset,
        "limit": limit,
        "total": len(results),
        "results": results
    }


@app.get("/jobs")
async def list_jobs(
    status: Optional[CrawlJobStatus] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """List crawl jobs"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    jobs = await orchestrator.list_jobs(status, limit)
    
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "start_urls": [str(url) for url in job.config.start_urls]
            }
            for job in jobs
        ]
    }


@app.get("/stats")
async def get_system_stats():
    """Get system statistics"""
    if not monitor:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = await monitor.get_system_stats()
    
    # Add worker pool status if available
    if worker_pool:
        stats["workers"] = worker_pool.get_status()
    
    return stats


@app.get("/stats/domain/{domain}")
async def get_domain_stats(domain: str):
    """Get statistics for a specific domain"""
    if not monitor:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = await monitor.get_domain_stats(domain)
    return stats


@app.post("/robots/check")
async def check_robots_txt(url: str, user_agent: Optional[str] = None):
    """Check if URL is allowed by robots.txt"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Initialize robots cache
    parser = RobotsParser(user_agent=user_agent or "LLMOptimizer")
    cache = RobotsCache(redis_client, parser)
    
    # Parse URL
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc
    
    # Check if allowed
    allowed = await cache.can_crawl(url, domain, user_agent)
    crawl_delay = await cache.get_crawl_delay(domain, user_agent)
    sitemaps = await cache.get_sitemaps(domain)
    
    return {
        "url": url,
        "domain": domain,
        "allowed": allowed,
        "crawl_delay": crawl_delay,
        "sitemaps": sitemaps
    }


@app.post("/test/crawl")
async def test_crawl_url(url: str):
    """Test crawling a single URL (for debugging)"""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    from src.crawler import WebCrawler
    
    crawler = WebCrawler()
    try:
        await crawler.start()
        result = await crawler.crawl(url)
        return result.to_dict()
    finally:
        await crawler.close()


class EnhancedCrawlRequest(BaseModel):
    """Request model for enhanced crawling"""
    url: HttpUrl
    render_javascript: Optional[bool] = None
    extraction_rules: Optional[str] = None
    check_duplicates: bool = True
    extract_structured_data: bool = True
    analyze_content: bool = True


@app.post("/enhanced/crawl")
async def enhanced_crawl_url(request: EnhancedCrawlRequest):
    """Crawl URL with enhanced features"""
    if not enhanced_crawler:
        raise HTTPException(
            status_code=503, 
            detail="Enhanced crawler not initialized. Set ENABLE_ENHANCED_CRAWLER=true"
        )
    
    result = await enhanced_crawler.crawl(
        str(request.url),
        render_javascript=request.render_javascript,
        extraction_rules=request.extraction_rules
    )
    
    return result.to_dict()


@app.post("/enhanced/batch")
async def enhanced_batch_crawl(urls: List[HttpUrl], render_javascript: Optional[bool] = None):
    """Crawl multiple URLs with enhanced features"""
    if not enhanced_crawler:
        raise HTTPException(
            status_code=503,
            detail="Enhanced crawler not initialized. Set ENABLE_ENHANCED_CRAWLER=true"
        )
    
    if len(urls) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 URLs per batch")
    
    results = await enhanced_crawler.crawl_batch(
        [str(url) for url in urls],
        render_javascript=render_javascript
    )
    
    return {
        "total": len(results),
        "results": [r.to_dict() for r in results]
    }


@app.get("/enhanced/stats")
async def get_enhanced_crawler_stats():
    """Get enhanced crawler statistics"""
    if not enhanced_crawler:
        raise HTTPException(
            status_code=503,
            detail="Enhanced crawler not initialized"
        )
    
    return enhanced_crawler.get_statistics()


@app.post("/content/detect")
async def detect_content_type(content: str, url: Optional[str] = None):
    """Detect content type and properties"""
    if not enhanced_crawler:
        raise HTTPException(status_code=503, detail="Enhanced crawler not initialized")
    
    content_bytes = content.encode('utf-8')
    result = await enhanced_crawler.content_detector.detect_content_type(
        content_bytes,
        url=url
    )
    
    return result


@app.post("/content/analyze")
async def analyze_content(content: str, mime_type: str = "text/html"):
    """Analyze content structure and quality"""
    if not enhanced_crawler:
        raise HTTPException(status_code=503, detail="Enhanced crawler not initialized")
    
    result = await enhanced_crawler.content_analyzer.analyze_content(
        content,
        mime_type
    )
    
    return result


@app.post("/content/extract-structured")
async def extract_structured_data(html: str, url: HttpUrl):
    """Extract structured data from HTML"""
    if not enhanced_crawler:
        raise HTTPException(status_code=503, detail="Enhanced crawler not initialized")
    
    result = await enhanced_crawler.structured_extractor.extract_all(
        html,
        str(url),
        extract_metadata=True
    )
    
    return result


@app.post("/content/filter")
async def filter_main_content(html: str):
    """Extract and filter main content from HTML"""
    if not enhanced_crawler:
        raise HTTPException(status_code=503, detail="Enhanced crawler not initialized")
    
    result = enhanced_crawler.content_filter.extract_main_content(
        html,
        remove_navigation=True,
        remove_ads=True,
        remove_comments=True
    )
    
    return result


@app.post("/content/check-duplicate")
async def check_duplicate_content(content: str, url: HttpUrl):
    """Check if content is duplicate"""
    if not enhanced_crawler or not enhanced_crawler.deduplicator:
        raise HTTPException(
            status_code=503,
            detail="Deduplication not enabled"
        )
    
    result = await enhanced_crawler.deduplicator.check_duplicate(
        content,
        str(url)
    )
    
    return result


@app.get("/browser/status")
async def get_browser_pool_status():
    """Get browser pool status"""
    if not browser_pool:
        raise HTTPException(
            status_code=503,
            detail="Browser pool not initialized. Set ENABLE_JS_RENDERING=true"
        )
    
    health = await browser_pool.health_check()
    metrics = browser_pool.get_metrics()
    
    return {
        "health": health,
        "metrics": metrics
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8003"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )