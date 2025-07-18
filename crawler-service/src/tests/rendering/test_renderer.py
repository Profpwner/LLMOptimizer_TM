"""Tests for JavaScript rendering module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import base64
from rendering.renderer import JavaScriptRenderer
from rendering.strategies import RenderingOptions, WaitStrategy
from rendering.browser_pool import BrowserPool


class TestJavaScriptRenderer:
    """Test cases for JavaScriptRenderer class."""
    
    @pytest.fixture
    def mock_browser_pool(self):
        """Create mock browser pool."""
        pool = Mock(spec=BrowserPool)
        return pool
    
    @pytest.fixture
    def renderer(self, mock_browser_pool):
        """Create JavaScriptRenderer instance."""
        return JavaScriptRenderer(mock_browser_pool)
    
    @pytest.fixture
    def mock_page(self):
        """Create mock Playwright page."""
        page = AsyncMock()
        page.url = 'https://example.com'
        page.content = AsyncMock(return_value='<html><body>Test content</body></html>')
        page.title = AsyncMock(return_value='Test Page')
        page.evaluate = AsyncMock(return_value={})
        page.screenshot = AsyncMock(return_value=b'fake_screenshot_data')
        page.goto = AsyncMock(return_value=Mock(status=200, headers={'content-type': 'text/html'}))
        page.wait_for_selector = AsyncMock()
        page.wait_for_function = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.set_extra_http_headers = AsyncMock()
        page.route = AsyncMock()
        page.on = Mock()
        return page
    
    @pytest.mark.asyncio
    async def test_render_basic_page(self, renderer, mock_browser_pool, mock_page):
        """Test basic page rendering."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        result = await renderer.render_page('https://example.com')
        
        assert result['success'] is True
        assert result['url'] == 'https://example.com'
        assert result['html'] == '<html><body>Test content</body></html>'
        assert result['title'] == 'Test Page'
        assert result['text'] == 'Test content'
        assert result['render_time'] > 0
        assert renderer.metrics['successful_renders'] == 1
    
    @pytest.mark.asyncio
    async def test_render_with_custom_headers(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with custom headers."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        headers = {'User-Agent': 'CustomBot/1.0'}
        result = await renderer.render_page('https://example.com', headers=headers)
        
        mock_page.set_extra_http_headers.assert_called_once_with(headers)
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_render_with_wait_strategy(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with different wait strategies."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(wait_strategy=WaitStrategy.NETWORKIDLE)
        result = await renderer.render_page('https://example.com', options=options)
        
        mock_page.wait_for_load_state.assert_called_with('networkidle', timeout=30000)
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_render_with_wait_for_selector(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with wait for specific selector."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(wait_for_selector='#content')
        result = await renderer.render_page('https://example.com', options=options)
        
        mock_page.wait_for_selector.assert_called_once_with('#content', timeout=30000)
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_render_with_screenshot(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with screenshot capture."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(take_screenshot=True, screenshot_full_page=True)
        result = await renderer.render_page('https://example.com', options=options)
        
        mock_page.screenshot.assert_called_once_with(full_page=True, type='png')
        assert result['success'] is True
        assert result['screenshot'] == base64.b64encode(b'fake_screenshot_data').decode()
        assert result['metadata']['screenshot_size'] == len(b'fake_screenshot_data')
    
    @pytest.mark.asyncio
    async def test_render_with_custom_scripts(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with custom script execution."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        custom_script = 'document.body.style.display = "none";'
        options = RenderingOptions(execute_scripts=[custom_script])
        
        result = await renderer.render_page('https://example.com', options=options)
        
        mock_page.evaluate.assert_any_call(custom_script)
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_render_with_resource_blocking(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with resource blocking."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(block_resources=['image', 'font'])
        result = await renderer.render_page('https://example.com', options=options)
        
        # Verify route was called for resource blocking
        assert mock_page.route.called
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_render_with_domain_filtering(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with domain filtering."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(
            allowed_domains=['example.com'],
            blocked_domains=['ads.example.com']
        )
        result = await renderer.render_page('https://example.com', options=options)
        
        # Verify route was called for domain filtering
        assert mock_page.route.called
        assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_render_with_network_monitoring(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with network activity monitoring."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(extract_network_logs=True)
        result = await renderer.render_page('https://example.com', options=options)
        
        # Verify network monitoring was set up
        assert mock_page.on.call_count >= 3  # request, response, requestfailed
        assert result['success'] is True
        assert 'network_activity' in result
    
    @pytest.mark.asyncio
    async def test_render_with_console_monitoring(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with console log monitoring."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        options = RenderingOptions(extract_console_logs=True)
        result = await renderer.render_page('https://example.com', options=options)
        
        # Verify console monitoring was set up
        mock_page.on.assert_any_call('console', mock_page.on.call_args_list[-1][0][1])
        assert result['success'] is True
        assert 'console_logs' in result
    
    @pytest.mark.asyncio
    async def test_render_timeout_error(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with timeout error."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        mock_page.goto.side_effect = PlaywrightTimeout("Navigation timeout")
        
        result = await renderer.render_page('https://example.com')
        
        assert result['success'] is False
        assert 'Timeout error' in result['error']
        assert renderer.metrics['timeout_errors'] == 1
        assert renderer.metrics['failed_renders'] == 1
    
    @pytest.mark.asyncio
    async def test_render_general_error(self, renderer, mock_browser_pool, mock_page):
        """Test rendering with general error."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        mock_page.goto.side_effect = Exception("Network error")
        
        result = await renderer.render_page('https://example.com')
        
        assert result['success'] is False
        assert 'Rendering error' in result['error']
        assert renderer.metrics['failed_renders'] == 1
    
    @pytest.mark.asyncio
    async def test_extract_page_metadata(self, renderer, mock_page):
        """Test page metadata extraction."""
        mock_metadata = {
            'metaTags': {'description': 'Test page'},
            'timing': {'domContentLoaded': 100, 'loadComplete': 200},
            'viewport': {'width': 1920, 'height': 1080},
            'document': {'readyState': 'complete'},
            'cookieCount': 3
        }
        mock_page.evaluate = AsyncMock(return_value=mock_metadata)
        
        metadata = await renderer._extract_page_metadata(mock_page)
        
        assert metadata == mock_metadata
        assert mock_page.evaluate.called
    
    @pytest.mark.asyncio
    async def test_extract_resources(self, renderer, mock_page):
        """Test resource extraction."""
        mock_resources = [
            {'type': 'image', 'url': '/image.jpg', 'width': 100, 'height': 100},
            {'type': 'script', 'url': '/script.js', 'async': False},
            {'type': 'stylesheet', 'url': '/style.css', 'media': 'all'}
        ]
        mock_page.evaluate = AsyncMock(return_value=mock_resources)
        mock_page.url = 'https://example.com/page'
        
        resources = await renderer._extract_resources(mock_page)
        
        assert len(resources) == 3
        # Check URLs are resolved
        assert resources[0]['url'] == 'https://example.com/image.jpg'
        assert resources[1]['url'] == 'https://example.com/script.js'
        assert resources[2]['url'] == 'https://example.com/style.css'
    
    @pytest.mark.asyncio
    async def test_render_multiple_urls(self, renderer, mock_browser_pool, mock_page):
        """Test rendering multiple URLs concurrently."""
        mock_browser_pool.acquire_page = AsyncMock()
        mock_browser_pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        mock_browser_pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        urls = ['https://example1.com', 'https://example2.com', 'https://example3.com']
        results = await renderer.render_multiple(urls, max_concurrent=2)
        
        assert len(results) == 3
        for result in results:
            assert result['success'] is True
    
    def test_get_metrics(self, renderer):
        """Test metrics retrieval."""
        renderer.metrics = {
            'total_renders': 10,
            'successful_renders': 8,
            'failed_renders': 2,
            'average_render_time': 1.5,
            'timeout_errors': 1
        }
        
        metrics = renderer.get_metrics()
        
        assert metrics['total_renders'] == 10
        assert metrics['successful_renders'] == 8
        assert metrics['failed_renders'] == 2
        assert metrics['success_rate'] == 0.8
        assert 'pool_metrics' in metrics
    
    @pytest.mark.asyncio
    async def test_navigate_with_retry(self, renderer, mock_page):
        """Test navigation with retry logic."""
        options = RenderingOptions()
        
        # First two attempts fail, third succeeds
        mock_page.goto = AsyncMock(side_effect=[
            Exception("Network error"),
            Exception("Timeout"),
            Mock(status=200)
        ])
        
        response = await renderer._navigate_with_retry(mock_page, 'https://example.com', options)
        
        assert response is not None
        assert response.status == 200
        assert mock_page.goto.call_count == 3
    
    @pytest.mark.asyncio
    async def test_navigate_with_retry_all_fail(self, renderer, mock_page):
        """Test navigation retry when all attempts fail."""
        options = RenderingOptions()
        
        mock_page.goto = AsyncMock(side_effect=Exception("Persistent error"))
        
        with pytest.raises(Exception):
            await renderer._navigate_with_retry(mock_page, 'https://example.com', options, max_retries=2)
        
        assert mock_page.goto.call_count == 3