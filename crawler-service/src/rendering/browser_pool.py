"""Browser pool management for efficient resource utilization."""

import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import time
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import structlog

logger = structlog.get_logger(__name__)


class BrowserPool:
    """Manages a pool of browser instances for parallel rendering."""
    
    def __init__(
        self,
        max_browsers: int = 3,
        max_contexts_per_browser: int = 5,
        browser_type: str = "chromium",
        headless: bool = True,
        stealth: bool = True
    ):
        """
        Initialize browser pool.
        
        Args:
            max_browsers: Maximum number of browser instances
            max_contexts_per_browser: Maximum contexts per browser
            browser_type: Browser type (chromium, firefox, webkit)
            headless: Run browsers in headless mode
            stealth: Use stealth mode to avoid detection
        """
        self.max_browsers = max_browsers
        self.max_contexts_per_browser = max_contexts_per_browser
        self.browser_type = browser_type
        self.headless = headless
        self.stealth = stealth
        
        self.playwright = None
        self.browsers: List[Browser] = []
        self.context_counts: Dict[Browser, int] = {}
        self.browser_lock = asyncio.Lock()
        self.shutdown_event = asyncio.Event()
        
        # Performance metrics
        self.metrics = {
            'total_requests': 0,
            'active_contexts': 0,
            'browser_launches': 0,
            'context_creations': 0,
            'errors': 0
        }
    
    async def start(self):
        """Start the browser pool."""
        logger.info("Starting browser pool", 
                   max_browsers=self.max_browsers,
                   browser_type=self.browser_type)
        
        self.playwright = await async_playwright().start()
        
        # Pre-launch minimum browsers
        min_browsers = min(2, self.max_browsers)
        for _ in range(min_browsers):
            await self._launch_browser()
    
    async def stop(self):
        """Stop the browser pool and clean up resources."""
        logger.info("Stopping browser pool")
        self.shutdown_event.set()
        
        # Close all browsers
        for browser in self.browsers:
            try:
                await browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
        
        self.browsers.clear()
        self.context_counts.clear()
        
        if self.playwright:
            await self.playwright.stop()
    
    async def _launch_browser(self) -> Browser:
        """Launch a new browser instance."""
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--disable-accelerated-2d-canvas',
            '--disable-features=IsolateOrigins,site-per-process',
            '--enable-features=NetworkService,NetworkServiceInProcess'
        ]
        
        if self.stealth:
            browser_args.extend([
                '--disable-blink-features=AutomationControlled',
                '--exclude-switches=enable-automation',
                '--disable-infobars'
            ])
        
        browser_options = {
            'headless': self.headless,
            'args': browser_args
        }
        
        # Add stealth-specific options
        if self.stealth:
            browser_options['chromium_sandbox'] = False
        
        # Launch browser based on type
        if self.browser_type == "chromium":
            browser = await self.playwright.chromium.launch(**browser_options)
        elif self.browser_type == "firefox":
            browser = await self.playwright.firefox.launch(**browser_options)
        elif self.browser_type == "webkit":
            browser = await self.playwright.webkit.launch(**browser_options)
        else:
            raise ValueError(f"Unknown browser type: {self.browser_type}")
        
        self.browsers.append(browser)
        self.context_counts[browser] = 0
        self.metrics['browser_launches'] += 1
        
        logger.info(f"Launched new {self.browser_type} browser", 
                   total_browsers=len(self.browsers))
        
        return browser
    
    @asynccontextmanager
    async def acquire_page(self, options: Optional[Dict[str, Any]] = None):
        """
        Acquire a page from the pool.
        
        Args:
            options: Browser context options
            
        Yields:
            Page instance
        """
        browser = None
        context = None
        page = None
        
        try:
            # Get or create browser
            async with self.browser_lock:
                browser = await self._get_available_browser()
                if not browser:
                    if len(self.browsers) < self.max_browsers:
                        browser = await self._launch_browser()
                    else:
                        # Wait for available browser
                        browser = await self._wait_for_browser()
                
                self.context_counts[browser] += 1
                self.metrics['active_contexts'] += 1
            
            # Create context with options
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'java_script_enabled': True,
                'ignore_https_errors': True,
                'bypass_csp': True
            }
            
            if options:
                context_options.update(options)
            
            if self.stealth:
                # Add stealth modifications
                context_options['extra_http_headers'] = {
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            
            context = await browser.new_context(**context_options)
            self.metrics['context_creations'] += 1
            
            # Apply stealth techniques to context
            if self.stealth:
                await self._apply_stealth_scripts(context)
            
            page = await context.new_page()
            self.metrics['total_requests'] += 1
            
            yield page
            
        except Exception as e:
            self.metrics['errors'] += 1
            logger.error(f"Error acquiring page: {e}")
            raise
        finally:
            # Cleanup
            if page:
                try:
                    await page.close()
                except:
                    pass
            
            if context:
                try:
                    await context.close()
                except:
                    pass
            
            if browser:
                async with self.browser_lock:
                    self.context_counts[browser] -= 1
                    self.metrics['active_contexts'] -= 1
    
    async def _get_available_browser(self) -> Optional[Browser]:
        """Get an available browser with capacity."""
        for browser in self.browsers:
            if browser.is_connected() and self.context_counts[browser] < self.max_contexts_per_browser:
                return browser
        return None
    
    async def _wait_for_browser(self, timeout: float = 30.0) -> Browser:
        """Wait for an available browser."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            browser = await self._get_available_browser()
            if browser:
                return browser
            
            await asyncio.sleep(0.1)
        
        raise TimeoutError("No available browser after timeout")
    
    async def _apply_stealth_scripts(self, context: BrowserContext):
        """Apply stealth scripts to avoid detection."""
        stealth_js = """
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Override navigator.plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {
                    0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Plugin"
                }
            ]
        });
        
        // Override navigator.languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Remove automation indicators
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Override console.debug
        const originalConsoleDebug = console.debug;
        console.debug = function(...args) {
            if (!args[0]?.includes('devtools')) {
                return originalConsoleDebug.apply(console, args);
            }
        };
        """
        
        await context.add_init_script(stealth_js)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get pool performance metrics."""
        return {
            **self.metrics,
            'active_browsers': len(self.browsers),
            'browsers_status': [
                {
                    'connected': browser.is_connected(),
                    'contexts': self.context_counts.get(browser, 0)
                }
                for browser in self.browsers
            ]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the pool."""
        healthy_browsers = sum(1 for b in self.browsers if b.is_connected())
        
        return {
            'healthy': healthy_browsers > 0,
            'total_browsers': len(self.browsers),
            'healthy_browsers': healthy_browsers,
            'capacity_used': sum(self.context_counts.values()) / (self.max_browsers * self.max_contexts_per_browser),
            'metrics': self.get_metrics()
        }