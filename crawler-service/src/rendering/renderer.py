"""JavaScript renderer using Playwright for dynamic content extraction."""

import asyncio
import base64
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
import time

from playwright.async_api import Page, Response, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import structlog

from .browser_pool import BrowserPool
from .strategies import (
    WaitStrategy, RenderingOptions, RenderingStrategies,
    NetworkMonitor, ConsoleMonitor
)

logger = structlog.get_logger(__name__)


class JavaScriptRenderer:
    """Renders JavaScript-heavy pages using Playwright."""
    
    def __init__(self, browser_pool: BrowserPool):
        """
        Initialize renderer with browser pool.
        
        Args:
            browser_pool: Browser pool instance
        """
        self.browser_pool = browser_pool
        self.strategies = RenderingStrategies()
        
        # Performance metrics
        self.metrics = {
            'total_renders': 0,
            'successful_renders': 0,
            'failed_renders': 0,
            'average_render_time': 0,
            'timeout_errors': 0
        }
    
    async def render_page(
        self,
        url: str,
        options: Optional[RenderingOptions] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Render a page with JavaScript execution.
        
        Args:
            url: URL to render
            options: Rendering options
            headers: Additional HTTP headers
            
        Returns:
            Rendered page data including HTML, resources, and metadata
        """
        if not options:
            options = RenderingOptions()
        
        start_time = time.time()
        result = {
            'url': url,
            'success': False,
            'html': None,
            'text': None,
            'title': None,
            'metadata': {},
            'resources': [],
            'screenshot': None,
            'console_logs': [],
            'network_activity': {},
            'error': None,
            'render_time': 0
        }
        
        try:
            async with self.browser_pool.acquire_page() as page:
                # Set up monitoring
                network_monitor = NetworkMonitor()
                console_monitor = ConsoleMonitor()
                
                if options.extract_network_logs:
                    page.on('request', network_monitor.on_request)
                    page.on('response', network_monitor.on_response)
                    page.on('requestfailed', network_monitor.on_request_failed)
                
                if options.extract_console_logs:
                    page.on('console', console_monitor.on_console)
                
                # Set up resource blocking
                if options.block_resources:
                    await page.route('**/*', 
                        self.strategies.create_resource_blocker(options.block_resources))
                
                # Set up domain filtering
                if options.allowed_domains or options.blocked_domains:
                    await page.route('**/*',
                        self.strategies.create_domain_filter(
                            options.allowed_domains,
                            options.blocked_domains
                        ))
                
                # Add custom headers
                if headers:
                    await page.set_extra_http_headers(headers)
                
                # Navigate to page
                response = await self._navigate_with_retry(page, url, options)
                
                if response:
                    result['metadata']['status_code'] = response.status
                    result['metadata']['headers'] = dict(response.headers)
                
                # Wait based on strategy
                await self._apply_wait_strategy(page, url, options)
                
                # Execute custom scripts
                for script in options.execute_scripts:
                    try:
                        await page.evaluate(script)
                    except Exception as e:
                        logger.warning(f"Error executing custom script: {e}")
                
                # Handle SPA navigation
                if options.wait_for_navigation and options.wait_strategy == WaitStrategy.AUTO:
                    detected_strategy = await self.strategies.auto_detect_strategy(page, url)
                    if detected_strategy == WaitStrategy.NETWORKIDLE:
                        await self.strategies.wait_for_spa_content(page, options.timeout)
                
                # Handle AJAX requests
                if options.intercept_ajax:
                    await self.strategies.wait_for_ajax_completion(page, options.ajax_timeout)
                
                # Scroll for lazy loading
                if options.wait_strategy == WaitStrategy.CUSTOM:
                    await self.strategies.scroll_to_load_content(page)
                
                # Extract content
                result['html'] = await page.content()
                result['title'] = await page.title()
                result['url'] = page.url  # May differ due to redirects
                
                # Extract text content
                soup = BeautifulSoup(result['html'], 'lxml')
                result['text'] = soup.get_text(separator=' ', strip=True)
                
                # Extract metadata
                result['metadata'].update(await self._extract_page_metadata(page))
                
                # Take screenshot
                if options.take_screenshot:
                    screenshot_data = await page.screenshot(
                        full_page=options.screenshot_full_page,
                        type=options.screenshot_format
                    )
                    result['screenshot'] = base64.b64encode(screenshot_data).decode()
                    result['metadata']['screenshot_size'] = len(screenshot_data)
                
                # Extract resources
                if options.extract_resources:
                    result['resources'] = await self._extract_resources(page)
                
                # Get monitoring data
                if options.extract_network_logs:
                    result['network_activity'] = network_monitor.get_summary()
                
                if options.extract_console_logs:
                    result['console_logs'] = console_monitor.logs
                    result['metadata']['has_console_errors'] = console_monitor.has_errors()
                
                result['success'] = True
                self.metrics['successful_renders'] += 1
                
        except PlaywrightTimeout as e:
            result['error'] = f"Timeout error: {str(e)}"
            self.metrics['timeout_errors'] += 1
            self.metrics['failed_renders'] += 1
            logger.error(f"Timeout rendering {url}: {e}")
            
        except Exception as e:
            result['error'] = f"Rendering error: {str(e)}"
            self.metrics['failed_renders'] += 1
            logger.error(f"Error rendering {url}: {e}")
        
        finally:
            # Calculate metrics
            render_time = time.time() - start_time
            result['render_time'] = render_time
            self.metrics['total_renders'] += 1
            
            # Update average render time
            if self.metrics['successful_renders'] > 0:
                self.metrics['average_render_time'] = (
                    (self.metrics['average_render_time'] * (self.metrics['successful_renders'] - 1) + render_time) /
                    self.metrics['successful_renders']
                )
        
        return result
    
    async def _navigate_with_retry(
        self,
        page: Page,
        url: str,
        options: RenderingOptions,
        max_retries: int = 2
    ) -> Optional[Response]:
        """Navigate to URL with retry logic."""
        for attempt in range(max_retries + 1):
            try:
                response = await page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=options.timeout
                )
                return response
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Navigation attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(1)
                else:
                    raise
        
        return None
    
    async def _apply_wait_strategy(
        self,
        page: Page,
        url: str,
        options: RenderingOptions
    ):
        """Apply the specified wait strategy."""
        if options.wait_for_selector:
            await page.wait_for_selector(
                options.wait_for_selector,
                timeout=options.timeout
            )
        
        elif options.wait_for_function:
            await page.wait_for_function(
                options.wait_for_function,
                timeout=options.timeout
            )
        
        elif options.wait_strategy == WaitStrategy.LOAD:
            await page.wait_for_load_state('load', timeout=options.timeout)
        
        elif options.wait_strategy == WaitStrategy.DOMCONTENTLOADED:
            await page.wait_for_load_state('domcontentloaded', timeout=options.timeout)
        
        elif options.wait_strategy == WaitStrategy.NETWORKIDLE:
            await page.wait_for_load_state('networkidle', timeout=options.timeout)
        
        elif options.wait_strategy == WaitStrategy.AUTO:
            # Auto detection is handled elsewhere
            pass
    
    async def _extract_page_metadata(self, page: Page) -> Dict[str, Any]:
        """Extract various page metadata."""
        metadata_js = """
        () => {
            const meta = {};
            
            // Get all meta tags
            const metaTags = {};
            document.querySelectorAll('meta').forEach(tag => {
                const name = tag.getAttribute('name') || tag.getAttribute('property');
                const content = tag.getAttribute('content');
                if (name && content) {
                    metaTags[name] = content;
                }
            });
            meta.metaTags = metaTags;
            
            // Get page timing
            if (window.performance && window.performance.timing) {
                const timing = window.performance.timing;
                meta.timing = {
                    domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                    loadComplete: timing.loadEventEnd - timing.navigationStart,
                    domInteractive: timing.domInteractive - timing.navigationStart
                };
            }
            
            // Get viewport
            meta.viewport = {
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio
            };
            
            // Get document info
            meta.document = {
                readyState: document.readyState,
                characterSet: document.characterSet,
                documentMode: document.documentMode,
                compatMode: document.compatMode
            };
            
            // Get cookies count (not values for privacy)
            meta.cookieCount = document.cookie ? document.cookie.split(';').length : 0;
            
            return meta;
        }
        """
        
        try:
            return await page.evaluate(metadata_js)
        except Exception as e:
            logger.warning(f"Error extracting metadata: {e}")
            return {}
    
    async def _extract_resources(self, page: Page) -> List[Dict[str, Any]]:
        """Extract information about loaded resources."""
        resources_js = """
        () => {
            const resources = [];
            
            // Get all images
            document.querySelectorAll('img').forEach(img => {
                resources.push({
                    type: 'image',
                    url: img.src,
                    alt: img.alt,
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                    loaded: img.complete
                });
            });
            
            // Get all scripts
            document.querySelectorAll('script[src]').forEach(script => {
                resources.push({
                    type: 'script',
                    url: script.src,
                    async: script.async,
                    defer: script.defer
                });
            });
            
            // Get all stylesheets
            document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
                resources.push({
                    type: 'stylesheet',
                    url: link.href,
                    media: link.media
                });
            });
            
            // Get all iframes
            document.querySelectorAll('iframe').forEach(iframe => {
                resources.push({
                    type: 'iframe',
                    url: iframe.src,
                    width: iframe.width,
                    height: iframe.height
                });
            });
            
            return resources;
        }
        """
        
        try:
            resources = await page.evaluate(resources_js)
            
            # Resolve relative URLs
            base_url = page.url
            for resource in resources:
                if resource['url']:
                    resource['url'] = urljoin(base_url, resource['url'])
            
            return resources
            
        except Exception as e:
            logger.warning(f"Error extracting resources: {e}")
            return []
    
    async def render_multiple(
        self,
        urls: List[str],
        options: Optional[RenderingOptions] = None,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Render multiple URLs concurrently.
        
        Args:
            urls: List of URLs to render
            options: Rendering options
            max_concurrent: Maximum concurrent renders
            
        Returns:
            List of render results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def render_with_semaphore(url):
            async with semaphore:
                return await self.render_page(url, options)
        
        tasks = [render_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get renderer performance metrics."""
        success_rate = (
            self.metrics['successful_renders'] / self.metrics['total_renders']
            if self.metrics['total_renders'] > 0 else 0
        )
        
        return {
            **self.metrics,
            'success_rate': round(success_rate, 2),
            'pool_metrics': self.browser_pool.get_metrics()
        }