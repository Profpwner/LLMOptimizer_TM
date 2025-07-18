"""Enhanced web crawler with advanced content processing capabilities."""

import asyncio
import time
from typing import Optional, List, Dict, Set, Any
from datetime import datetime
from urllib.parse import urlparse, urljoin

import aiohttp
from aiohttp import ClientTimeout
import structlog
from redis import asyncio as aioredis

from .crawler import WebCrawler, CrawlResult
from ..content import ContentDetector, ContentAnalyzer
from ..rendering import BrowserPool, JavaScriptRenderer, RenderingOptions, WaitStrategy
from ..extraction import StructuredDataExtractor, RuleEngine, ContentFilter
from ..deduplication import ContentDeduplicator, DuplicationPolicy

logger = structlog.get_logger(__name__)


class EnhancedCrawlResult(CrawlResult):
    """Extended crawl result with advanced processing data."""
    
    def __init__(self, base_result: CrawlResult):
        """Initialize from base crawl result."""
        super().__init__(
            url=base_result.url,
            status_code=base_result.status_code,
            content=base_result.content,
            content_type=base_result.content_type,
            content_length=base_result.content_length,
            links=base_result.links,
            images=base_result.images,
            title=base_result.title,
            meta_description=base_result.meta_description,
            headers=base_result.headers,
            crawl_time=base_result.crawl_time,
            error=base_result.error,
            redirect_chain=base_result.redirect_chain
        )
        
        # Advanced processing results
        self.content_detection: Optional[Dict[str, Any]] = None
        self.content_analysis: Optional[Dict[str, Any]] = None
        self.structured_data: Optional[Dict[str, Any]] = None
        self.main_content: Optional[Dict[str, Any]] = None
        self.duplication_check: Optional[Dict[str, Any]] = None
        self.javascript_rendered: bool = False
        self.processing_time: Dict[str, float] = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary with enhanced data."""
        base_dict = super().to_dict()
        base_dict.update({
            'content_detection': self.content_detection,
            'content_analysis': self.content_analysis,
            'structured_data': self.structured_data,
            'main_content': self.main_content,
            'duplication_check': self.duplication_check,
            'javascript_rendered': self.javascript_rendered,
            'processing_time': self.processing_time
        })
        return base_dict


class EnhancedWebCrawler:
    """Web crawler with advanced content processing capabilities."""
    
    def __init__(
        self,
        base_crawler: Optional[WebCrawler] = None,
        redis_client: Optional[aioredis.Redis] = None,
        enable_javascript: bool = True,
        enable_deduplication: bool = True,
        enable_content_analysis: bool = True,
        enable_structured_extraction: bool = True,
        browser_pool_size: int = 3,
        deduplication_policy: Optional[DuplicationPolicy] = None
    ):
        """
        Initialize enhanced crawler.
        
        Args:
            base_crawler: Base crawler instance
            redis_client: Redis client for caching
            enable_javascript: Enable JavaScript rendering
            enable_deduplication: Enable content deduplication
            enable_content_analysis: Enable content analysis
            enable_structured_extraction: Enable structured data extraction
            browser_pool_size: Size of browser pool for JS rendering
            deduplication_policy: Deduplication policy
        """
        self.base_crawler = base_crawler or WebCrawler()
        self.redis = redis_client
        
        # Feature flags
        self.enable_javascript = enable_javascript
        self.enable_deduplication = enable_deduplication
        self.enable_content_analysis = enable_content_analysis
        self.enable_structured_extraction = enable_structured_extraction
        
        # Initialize components
        self.content_detector = ContentDetector()
        self.content_analyzer = ContentAnalyzer()
        self.structured_extractor = StructuredDataExtractor()
        self.content_filter = ContentFilter()
        self.rule_engine = RuleEngine()
        
        # Browser pool for JS rendering
        self.browser_pool = None
        if enable_javascript:
            self.browser_pool = BrowserPool(max_browsers=browser_pool_size)
            self.js_renderer = JavaScriptRenderer(self.browser_pool)
        
        # Deduplication
        self.deduplicator = None
        if enable_deduplication:
            self.deduplicator = ContentDeduplicator(
                redis_client=redis_client,
                policy=deduplication_policy
            )
        
        # Statistics
        self.stats = {
            'total_crawled': 0,
            'js_rendered': 0,
            'duplicates_found': 0,
            'unique_content': 0,
            'processing_errors': 0
        }
        
        # Initialize common extraction rules
        self._initialize_extraction_rules()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self):
        """Start enhanced crawler."""
        await self.base_crawler.start()
        
        if self.browser_pool:
            await self.browser_pool.start()
            logger.info("Browser pool started")
        
        logger.info("Enhanced crawler started")
    
    async def close(self):
        """Close enhanced crawler."""
        await self.base_crawler.close()
        
        if self.browser_pool:
            await self.browser_pool.stop()
            logger.info("Browser pool stopped")
        
        logger.info("Enhanced crawler closed")
    
    def _initialize_extraction_rules(self):
        """Initialize common extraction rules."""
        common_rules = self.rule_engine.create_common_rules()
        for category, rules in common_rules.items():
            self.rule_engine.register_rules(category, rules)
    
    async def crawl(
        self,
        url: str,
        render_javascript: Optional[bool] = None,
        extraction_rules: Optional[str] = None
    ) -> EnhancedCrawlResult:
        """
        Crawl URL with enhanced processing.
        
        Args:
            url: URL to crawl
            render_javascript: Override JS rendering setting
            extraction_rules: Specific extraction rules category
            
        Returns:
            Enhanced crawl result
        """
        self.stats['total_crawled'] += 1
        start_time = time.time()
        
        # Determine if JS rendering is needed
        use_js = render_javascript if render_javascript is not None else self.enable_javascript
        
        # Perform base crawl or JS rendering
        if use_js and self.browser_pool:
            result = await self._crawl_with_javascript(url)
        else:
            base_result = await self.base_crawler.crawl(url)
            result = EnhancedCrawlResult(base_result)
        
        # Skip processing if crawl failed
        if result.error or not result.content:
            return result
        
        # Process content in parallel where possible
        processing_tasks = []
        
        # Content detection and analysis
        if self.enable_content_analysis:
            processing_tasks.append(self._process_content_detection(result))
        
        # Structured data extraction
        if self.enable_structured_extraction:
            processing_tasks.append(self._process_structured_extraction(result))
        
        # Main content extraction
        processing_tasks.append(self._process_main_content(result))
        
        # Run processing tasks
        await asyncio.gather(*processing_tasks, return_exceptions=True)
        
        # Content analysis (depends on detection)
        if self.enable_content_analysis and result.content_detection:
            await self._process_content_analysis(result)
        
        # Deduplication check
        if self.enable_deduplication and self.deduplicator:
            await self._process_deduplication(result)
        
        # Custom extraction rules
        if extraction_rules:
            await self._apply_extraction_rules(result, extraction_rules)
        
        # Calculate total processing time
        result.processing_time['total'] = time.time() - start_time
        
        return result
    
    async def _crawl_with_javascript(self, url: str) -> EnhancedCrawlResult:
        """Crawl with JavaScript rendering."""
        render_start = time.time()
        
        # Configure rendering options
        options = RenderingOptions(
            wait_strategy=WaitStrategy.AUTO,
            timeout=30000,
            block_resources=['font', 'media'],
            intercept_ajax=True,
            extract_resources=True,
            extract_console_logs=True,
            take_screenshot=False
        )
        
        # Render page
        render_result = await self.js_renderer.render_page(url, options)
        
        # Create enhanced result
        result = EnhancedCrawlResult(CrawlResult(
            url=render_result['url'],
            status_code=render_result['metadata'].get('status_code', 200),
            content=render_result['html'],
            content_type='text/html',
            content_length=len(render_result['html']) if render_result['html'] else 0,
            title=render_result['title'],
            headers=render_result['metadata'].get('headers', {}),
            crawl_time=render_result['render_time'],
            error=render_result['error']
        ))
        
        # Extract links from rendered content
        if render_result['html']:
            self.base_crawler._extract_content(result, result.url)
        
        # Add resources as images
        if render_result['resources']:
            for resource in render_result['resources']:
                if resource['type'] == 'image' and resource['url']:
                    result.images.append(resource['url'])
        
        result.javascript_rendered = True
        result.processing_time['js_rendering'] = time.time() - render_start
        self.stats['js_rendered'] += 1
        
        return result
    
    async def _process_content_detection(self, result: EnhancedCrawlResult):
        """Process content type detection."""
        try:
            detect_start = time.time()
            
            content_bytes = result.content.encode('utf-8') if result.content else b''
            result.content_detection = await self.content_detector.detect_content_type(
                content_bytes,
                url=result.url,
                headers=result.headers
            )
            
            result.processing_time['content_detection'] = time.time() - detect_start
            
        except Exception as e:
            logger.error(f"Content detection error: {e}", url=result.url)
            self.stats['processing_errors'] += 1
    
    async def _process_content_analysis(self, result: EnhancedCrawlResult):
        """Process content analysis."""
        try:
            analysis_start = time.time()
            
            mime_type = result.content_detection.get('mime_type', 'text/html')
            language = result.content_detection.get('language')
            
            result.content_analysis = await self.content_analyzer.analyze_content(
                result.content,
                mime_type,
                language
            )
            
            result.processing_time['content_analysis'] = time.time() - analysis_start
            
        except Exception as e:
            logger.error(f"Content analysis error: {e}", url=result.url)
            self.stats['processing_errors'] += 1
    
    async def _process_structured_extraction(self, result: EnhancedCrawlResult):
        """Process structured data extraction."""
        try:
            extraction_start = time.time()
            
            result.structured_data = await self.structured_extractor.extract_all(
                result.content,
                result.url,
                extract_metadata=True
            )
            
            result.processing_time['structured_extraction'] = time.time() - extraction_start
            
        except Exception as e:
            logger.error(f"Structured extraction error: {e}", url=result.url)
            self.stats['processing_errors'] += 1
    
    async def _process_main_content(self, result: EnhancedCrawlResult):
        """Process main content extraction."""
        try:
            filter_start = time.time()
            
            result.main_content = self.content_filter.extract_main_content(
                result.content,
                remove_navigation=True,
                remove_ads=True,
                remove_comments=True
            )
            
            result.processing_time['content_filtering'] = time.time() - filter_start
            
        except Exception as e:
            logger.error(f"Content filtering error: {e}", url=result.url)
            self.stats['processing_errors'] += 1
    
    async def _process_deduplication(self, result: EnhancedCrawlResult):
        """Process content deduplication."""
        try:
            dedup_start = time.time()
            
            # Use main content if available, otherwise full content
            content_to_check = (
                result.main_content['main_content']['text'] 
                if result.main_content and result.main_content.get('main_content')
                else result.content
            )
            
            metadata = {
                'canonical_url': result.structured_data.get('canonical_url') if result.structured_data else None
            }
            
            result.duplication_check = await self.deduplicator.check_duplicate(
                content_to_check,
                result.url,
                metadata
            )
            
            if result.duplication_check['is_duplicate']:
                self.stats['duplicates_found'] += 1
            else:
                self.stats['unique_content'] += 1
            
            result.processing_time['deduplication'] = time.time() - dedup_start
            
        except Exception as e:
            logger.error(f"Deduplication error: {e}", url=result.url)
            self.stats['processing_errors'] += 1
    
    async def _apply_extraction_rules(self, result: EnhancedCrawlResult, category: str):
        """Apply custom extraction rules."""
        try:
            rules_start = time.time()
            
            extracted_data = await self.rule_engine.extract(
                result.content,
                category,
                content_type='html'
            )
            
            if not hasattr(result, 'custom_extractions'):
                result.custom_extractions = {}
            
            result.custom_extractions[category] = extracted_data
            result.processing_time[f'rules_{category}'] = time.time() - rules_start
            
        except Exception as e:
            logger.error(f"Rule extraction error: {e}", url=result.url, category=category)
            self.stats['processing_errors'] += 1
    
    async def crawl_batch(
        self,
        urls: List[str],
        render_javascript: Optional[bool] = None
    ) -> List[EnhancedCrawlResult]:
        """Crawl multiple URLs with enhanced processing."""
        tasks = [
            self.crawl(url, render_javascript=render_javascript)
            for url in urls
        ]
        return await asyncio.gather(*tasks)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get crawler statistics."""
        stats = self.stats.copy()
        
        # Add component statistics
        if self.content_detector:
            stats['content_detection'] = self.content_detector.get_content_hash
        
        if self.structured_extractor:
            stats['structured_extraction'] = self.structured_extractor.get_statistics()
        
        if self.deduplicator:
            stats['deduplication'] = self.deduplicator.get_statistics()
        
        if self.js_renderer:
            stats['js_rendering'] = self.js_renderer.get_metrics()
        
        if self.rule_engine:
            stats['extraction_rules'] = self.rule_engine.get_statistics()
        
        return stats