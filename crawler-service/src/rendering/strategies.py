"""Rendering strategies and wait conditions for dynamic content."""

from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Union
from dataclasses import dataclass, field
import asyncio
import re

from playwright.async_api import Page, Response
import structlog

logger = structlog.get_logger(__name__)


class WaitStrategy(Enum):
    """Wait strategies for page loading."""
    LOAD = "load"  # Wait for load event
    DOMCONTENTLOADED = "domcontentloaded"  # Wait for DOMContentLoaded
    NETWORKIDLE = "networkidle"  # Wait for network to be idle
    CUSTOM = "custom"  # Custom wait function
    AUTO = "auto"  # Automatically detect best strategy


@dataclass
class RenderingOptions:
    """Options for JavaScript rendering."""
    
    # Basic options
    timeout: int = 30000  # Maximum time to wait (ms)
    wait_strategy: WaitStrategy = WaitStrategy.AUTO
    wait_for_selector: Optional[str] = None  # CSS selector to wait for
    wait_for_function: Optional[str] = None  # JavaScript function to evaluate
    
    # Resource handling
    block_resources: List[str] = field(default_factory=lambda: ['font', 'image', 'media'])
    allowed_domains: Optional[List[str]] = None  # Whitelist domains
    blocked_domains: Optional[List[str]] = None  # Blacklist domains
    
    # JavaScript execution
    execute_scripts: List[str] = field(default_factory=list)  # Scripts to run after load
    disable_javascript: bool = False
    
    # SPA handling
    wait_for_navigation: bool = True
    intercept_ajax: bool = True
    ajax_timeout: int = 5000  # Time to wait for AJAX requests
    
    # Screenshot options
    take_screenshot: bool = False
    screenshot_full_page: bool = True
    screenshot_format: str = "png"
    
    # Performance options
    cache_enabled: bool = True
    cookies_enabled: bool = True
    
    # Content extraction
    extract_resources: bool = False  # Extract loaded resources info
    extract_console_logs: bool = False
    extract_network_logs: bool = False


class RenderingStrategies:
    """Collection of rendering strategies for different scenarios."""
    
    @staticmethod
    async def auto_detect_strategy(page: Page, url: str) -> WaitStrategy:
        """Automatically detect the best wait strategy for a page."""
        # Check for common SPA frameworks
        spa_indicators = [
            'react', 'angular', 'vue', 'ember', 'backbone',
            'knockout', 'meteor', 'polymer'
        ]
        
        # Quick check in initial HTML
        try:
            content = await page.content()
            content_lower = content.lower()
            
            # Check for SPA indicators
            for indicator in spa_indicators:
                if indicator in content_lower:
                    logger.info(f"Detected {indicator} app, using NETWORKIDLE strategy")
                    return WaitStrategy.NETWORKIDLE
            
            # Check for lazy loading
            if 'lazy' in content_lower or 'infinite-scroll' in content_lower:
                logger.info("Detected lazy loading, using CUSTOM strategy")
                return WaitStrategy.CUSTOM
            
        except Exception as e:
            logger.warning(f"Error detecting strategy: {e}")
        
        # Default to LOAD for regular pages
        return WaitStrategy.LOAD
    
    @staticmethod
    async def wait_for_spa_content(page: Page, timeout: int = 30000):
        """Wait for SPA content to load."""
        # Wait for common SPA ready indicators
        spa_ready_checks = [
            # React
            "window.React && window.React.version",
            # Angular
            "window.angular && window.angular.version",
            # Vue
            "window.Vue && window.Vue.version",
            # Generic app ready
            "document.querySelector('[data-app-ready]')",
            "window.__APP_READY__",
            "window.appReady"
        ]
        
        for check in spa_ready_checks:
            try:
                result = await page.evaluate(check, timeout=1000)
                if result:
                    logger.info(f"SPA ready check passed: {check}")
                    break
            except:
                continue
        
        # Additional wait for content
        await page.wait_for_load_state('networkidle', timeout=timeout)
    
    @staticmethod
    async def wait_for_ajax_completion(page: Page, timeout: int = 5000):
        """Wait for AJAX requests to complete."""
        ajax_complete_js = """
        () => {
            return new Promise((resolve) => {
                let pendingRequests = 0;
                const checkInterval = 100;
                let lastActivity = Date.now();
                
                // Override XMLHttpRequest
                const originalOpen = XMLHttpRequest.prototype.open;
                const originalSend = XMLHttpRequest.prototype.send;
                
                XMLHttpRequest.prototype.open = function() {
                    this.addEventListener('loadstart', () => {
                        pendingRequests++;
                        lastActivity = Date.now();
                    });
                    
                    this.addEventListener('loadend', () => {
                        pendingRequests--;
                        lastActivity = Date.now();
                    });
                    
                    return originalOpen.apply(this, arguments);
                };
                
                XMLHttpRequest.prototype.send = function() {
                    return originalSend.apply(this, arguments);
                };
                
                // Override fetch
                const originalFetch = window.fetch;
                window.fetch = function() {
                    pendingRequests++;
                    lastActivity = Date.now();
                    
                    return originalFetch.apply(this, arguments)
                        .finally(() => {
                            pendingRequests--;
                            lastActivity = Date.now();
                        });
                };
                
                // Check for completion
                const checkComplete = setInterval(() => {
                    const timeSinceLastActivity = Date.now() - lastActivity;
                    
                    if (pendingRequests === 0 && timeSinceLastActivity > 500) {
                        clearInterval(checkComplete);
                        resolve(true);
                    }
                }, checkInterval);
                
                // Timeout
                setTimeout(() => {
                    clearInterval(checkComplete);
                    resolve(false);
                }, %d);
            });
        }
        """ % timeout
        
        try:
            await page.evaluate(ajax_complete_js)
        except Exception as e:
            logger.warning(f"Error waiting for AJAX: {e}")
    
    @staticmethod
    async def scroll_to_load_content(page: Page, max_scrolls: int = 10):
        """Scroll page to trigger lazy loading."""
        scroll_js = """
        async () => {
            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
            const getScrollHeight = () => document.documentElement.scrollHeight;
            
            let previousHeight = getScrollHeight();
            let scrollCount = 0;
            
            while (scrollCount < %d) {
                window.scrollTo(0, previousHeight);
                await delay(1000);
                
                const newHeight = getScrollHeight();
                if (newHeight === previousHeight) {
                    // No new content loaded
                    break;
                }
                
                previousHeight = newHeight;
                scrollCount++;
            }
            
            // Scroll back to top
            window.scrollTo(0, 0);
            return scrollCount;
        }
        """ % max_scrolls
        
        try:
            scrolls = await page.evaluate(scroll_js)
            logger.info(f"Performed {scrolls} scrolls to load content")
        except Exception as e:
            logger.warning(f"Error during scroll loading: {e}")
    
    @staticmethod
    def create_resource_blocker(blocked_types: List[str]) -> Callable:
        """Create a resource blocking handler."""
        async def block_resources(route):
            if route.request.resource_type in blocked_types:
                await route.abort()
            else:
                await route.continue_()
        
        return block_resources
    
    @staticmethod
    def create_domain_filter(
        allowed: Optional[List[str]] = None,
        blocked: Optional[List[str]] = None
    ) -> Callable:
        """Create a domain filtering handler."""
        async def filter_domains(route):
            url = route.request.url
            domain = re.search(r'https?://([^/]+)', url)
            
            if domain:
                domain = domain.group(1)
                
                if blocked and any(b in domain for b in blocked):
                    await route.abort()
                elif allowed and not any(a in domain for a in allowed):
                    await route.abort()
                else:
                    await route.continue_()
            else:
                await route.continue_()
        
        return filter_domains


class NetworkMonitor:
    """Monitor network activity during page rendering."""
    
    def __init__(self):
        self.requests: List[Dict[str, Any]] = []
        self.responses: List[Dict[str, Any]] = []
        self.failed_requests: List[Dict[str, Any]] = []
        
    async def on_request(self, request):
        """Handle request event."""
        self.requests.append({
            'url': request.url,
            'method': request.method,
            'resource_type': request.resource_type,
            'timestamp': asyncio.get_event_loop().time()
        })
    
    async def on_response(self, response: Response):
        """Handle response event."""
        self.responses.append({
            'url': response.url,
            'status': response.status,
            'headers': dict(response.headers),
            'timestamp': asyncio.get_event_loop().time()
        })
    
    async def on_request_failed(self, request):
        """Handle failed request event."""
        self.failed_requests.append({
            'url': request.url,
            'failure': request.failure,
            'timestamp': asyncio.get_event_loop().time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get network activity summary."""
        return {
            'total_requests': len(self.requests),
            'total_responses': len(self.responses),
            'failed_requests': len(self.failed_requests),
            'resource_types': self._count_resource_types(),
            'status_codes': self._count_status_codes(),
            'domains': self._extract_domains()
        }
    
    def _count_resource_types(self) -> Dict[str, int]:
        """Count requests by resource type."""
        types = {}
        for req in self.requests:
            resource_type = req['resource_type']
            types[resource_type] = types.get(resource_type, 0) + 1
        return types
    
    def _count_status_codes(self) -> Dict[str, int]:
        """Count responses by status code."""
        codes = {}
        for resp in self.responses:
            status = str(resp['status'])
            codes[status] = codes.get(status, 0) + 1
        return codes
    
    def _extract_domains(self) -> List[str]:
        """Extract unique domains from requests."""
        domains = set()
        for req in self.requests:
            match = re.search(r'https?://([^/]+)', req['url'])
            if match:
                domains.add(match.group(1))
        return sorted(list(domains))


class ConsoleMonitor:
    """Monitor console logs during rendering."""
    
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        
    async def on_console(self, msg):
        """Handle console message."""
        self.logs.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location,
            'timestamp': asyncio.get_event_loop().time()
        })
    
    def get_logs_by_type(self, log_type: str) -> List[Dict[str, Any]]:
        """Get logs filtered by type."""
        return [log for log in self.logs if log['type'] == log_type]
    
    def has_errors(self) -> bool:
        """Check if there are any error logs."""
        return any(log['type'] == 'error' for log in self.logs)