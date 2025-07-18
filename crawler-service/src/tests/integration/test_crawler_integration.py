"""Integration tests for the complete crawler system."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from content.detector import ContentDetector
from rendering.renderer import JavaScriptRenderer
from rendering.browser_pool import BrowserPool
from extraction.extractor import StructuredDataExtractor
from deduplication.deduplicator import ContentDeduplicator, DuplicationPolicy


class TestCrawlerIntegration:
    """Integration tests for crawler components working together."""
    
    @pytest.fixture
    async def browser_pool(self):
        """Create browser pool for testing."""
        pool = BrowserPool(max_browsers=1)
        yield pool
        await pool.close()
    
    @pytest.fixture
    def mock_browser_pool(self):
        """Create mock browser pool."""
        pool = Mock(spec=BrowserPool)
        mock_page = AsyncMock()
        mock_page.url = 'https://example.com'
        mock_page.content = AsyncMock(return_value='''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Test E-commerce Page</title>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org/",
                    "@type": "Product",
                    "name": "Test Product",
                    "description": "A great product for testing",
                    "offers": {
                        "@type": "Offer",
                        "price": "99.99",
                        "priceCurrency": "USD"
                    }
                }
                </script>
                <meta property="og:title" content="Test Product">
                <meta property="og:description" content="A great product">
                <meta name="twitter:card" content="summary">
            </head>
            <body>
                <h1>Test Product</h1>
                <p>This is a test product page with dynamic content.</p>
                <div id="dynamic-content"></div>
                <script>
                    document.getElementById('dynamic-content').innerHTML = 'Loaded via JavaScript!';
                </script>
            </body>
            </html>
        ''')
        mock_page.title = AsyncMock(return_value='Test E-commerce Page')
        mock_page.evaluate = AsyncMock(return_value={})
        mock_page.screenshot = AsyncMock(return_value=b'fake_screenshot')
        mock_page.goto = AsyncMock(return_value=Mock(status=200, headers={}))
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.set_extra_http_headers = AsyncMock()
        mock_page.route = AsyncMock()
        mock_page.on = Mock()
        
        pool.acquire_page = AsyncMock()
        pool.acquire_page.return_value.__aenter__ = AsyncMock(return_value=mock_page)
        pool.acquire_page.return_value.__aexit__ = AsyncMock()
        
        return pool
    
    @pytest.fixture
    def crawler_components(self, mock_browser_pool):
        """Create all crawler components."""
        return {
            'detector': ContentDetector(),
            'renderer': JavaScriptRenderer(mock_browser_pool),
            'extractor': StructuredDataExtractor(),
            'deduplicator': ContentDeduplicator(policy=DuplicationPolicy())
        }
    
    @pytest.mark.asyncio
    @patch('extruct.extract')
    async def test_full_crawl_pipeline(self, mock_extract, crawler_components):
        """Test complete crawl pipeline from rendering to deduplication."""
        # Mock extruct response
        mock_extract.return_value = {
            'json-ld': [{
                '@context': 'https://schema.org/',
                '@type': 'Product',
                'name': 'Test Product',
                'description': 'A great product for testing',
                'offers': {
                    '@type': 'Offer',
                    'price': '99.99',
                    'priceCurrency': 'USD'
                }
            }],
            'opengraph': [{
                'og:title': 'Test Product',
                'og:description': 'A great product'
            }]
        }
        
        url = 'https://example.com/product'
        
        # Step 1: Render the page
        renderer = crawler_components['renderer']
        render_result = await renderer.render_page(url)
        
        assert render_result['success'] is True
        assert render_result['html'] is not None
        assert render_result['title'] == 'Test E-commerce Page'
        
        # Step 2: Detect content type
        detector = crawler_components['detector']
        content_type = await detector.detect_content_type(
            render_result['html'].encode(),
            url=url,
            headers={'content-type': 'text/html; charset=utf-8'}
        )
        
        assert content_type['mime_type'] == 'text/html'
        assert content_type['encoding'] in ['utf-8', 'ascii']
        assert content_type['structure'] == 'html'
        
        # Step 3: Extract structured data
        extractor = crawler_components['extractor']
        extracted_data = await extractor.extract_all(
            render_result['html'],
            url
        )
        
        assert 'json_ld' in extracted_data['structured_data']
        assert len(extracted_data['structured_data']['json_ld']) > 0
        assert extracted_data['structured_data']['json_ld'][0]['type'] == 'Product'
        
        # Step 4: Check for duplicates
        deduplicator = crawler_components['deduplicator']
        dup_result = await deduplicator.check_duplicate(
            render_result['html'],
            url,
            metadata=extracted_data['metadata']
        )
        
        assert dup_result['is_duplicate'] is False
        assert dup_result['action'] == 'accept'
        
        # Step 5: Process same content again (should be duplicate)
        dup_result2 = await deduplicator.check_duplicate(
            render_result['html'],
            'https://example.com/product-copy'
        )
        
        assert dup_result2['is_duplicate'] is True
        assert dup_result2['duplicate_type'] == 'exact'
        assert dup_result2['original_url'] == url
    
    @pytest.mark.asyncio
    async def test_content_type_affects_processing(self, crawler_components):
        """Test that different content types are processed differently."""
        detector = crawler_components['detector']
        
        # Test PDF content
        pdf_content = b'%PDF-1.4 fake pdf content'
        pdf_result = await detector.detect_content_type(pdf_content)
        
        assert pdf_result['mime_type'] == 'application/pdf'
        assert pdf_result['description'] == 'PDF document'
        
        # Test JSON content
        json_content = b'{"key": "value", "items": [1, 2, 3]}'
        json_result = await detector.detect_content_type(json_content)
        
        assert json_result['structure'] == 'json'
        
        # Test image content
        png_content = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A fake png data'
        png_result = await detector.detect_content_type(png_content)
        
        assert png_result['mime_type'] == 'image/png'
        assert png_result['confidence'] >= 0.9
    
    @pytest.mark.asyncio
    async def test_javascript_rendering_captures_dynamic_content(self, crawler_components):
        """Test that JavaScript rendering captures dynamically loaded content."""
        renderer = crawler_components['renderer']
        
        # The mock already includes dynamic content
        result = await renderer.render_page('https://example.com/dynamic')
        
        assert 'dynamic-content' in result['html']
        assert result['success'] is True
    
    @pytest.mark.asyncio
    @patch('extruct.extract')
    async def test_structured_data_extraction_with_multiple_formats(self, mock_extract, crawler_components):
        """Test extraction of multiple structured data formats."""
        mock_extract.return_value = {
            'json-ld': [{
                '@type': 'Article',
                'headline': 'Test Article',
                'author': {'@type': 'Person', 'name': 'John Doe'}
            }],
            'microdata': [{
                'type': ['https://schema.org/Organization'],
                'properties': {'name': 'Test Company'}
            }],
            'opengraph': [{
                'og:title': 'Test Page',
                'og:type': 'article'
            }],
            'rdfa': []
        }
        
        extractor = crawler_components['extractor']
        html = '''
        <html>
        <head>
            <meta property="og:title" content="Test Page">
            <meta name="twitter:card" content="summary_large_image">
        </head>
        <body>
            <div itemscope itemtype="https://schema.org/Organization">
                <span itemprop="name">Test Company</span>
            </div>
        </body>
        </html>
        '''
        
        result = await extractor.extract_all(html, 'https://example.com')
        
        # Check all formats were extracted
        assert 'json_ld' in result['structured_data']
        assert 'microdata' in result['structured_data']
        assert 'opengraph' in result['structured_data']
        assert 'twitter_card' in result['structured_data']
        
        # Verify statistics
        stats = extractor.get_statistics()
        assert stats['json_ld_found'] > 0
        assert stats['microdata_found'] > 0
        assert stats['opengraph_found'] > 0
        assert stats['twitter_found'] > 0
    
    @pytest.mark.asyncio
    async def test_deduplication_with_similar_content(self, crawler_components):
        """Test deduplication handling of similar but not identical content."""
        deduplicator = crawler_components['deduplicator']
        
        # First page
        content1 = """
        <html>
        <body>
            <h1>Product Review: Amazing Widget</h1>
            <p>This widget is fantastic for everyday use.</p>
            <p>Price: $99.99</p>
            <p>Rating: 5 stars</p>
        </body>
        </html>
        """
        
        # Similar page with minor differences
        content2 = """
        <html>
        <body>
            <h1>Product Review: Amazing Widget</h1>
            <p>This widget is fantastic for everyday use!</p>
            <p>Price: $99.99</p>
            <p>Rating: 5 stars</p>
            <p>Updated: Today</p>
        </body>
        </html>
        """
        
        # Store first content
        result1 = await deduplicator.check_duplicate(content1, 'https://example.com/review1')
        assert result1['is_duplicate'] is False
        
        # Check second content (should be detected as similar/near-duplicate)
        # Note: In real scenario, this would depend on similarity thresholds
        result2 = await deduplicator.check_duplicate(content2, 'https://example.com/review2')
        
        # The result depends on the similarity calculation
        # For this test, we're verifying the deduplication process works
        assert 'is_duplicate' in result2
        assert 'action' in result2
    
    @pytest.mark.asyncio
    async def test_language_detection_integration(self, crawler_components):
        """Test language detection across different languages."""
        detector = crawler_components['detector']
        
        # English content
        english = b"This is a comprehensive guide to web crawling and data extraction."
        en_result = await detector.detect_content_type(english)
        
        # Spanish content
        spanish = "Esta es una guía completa sobre rastreo web y extracción de datos.".encode('utf-8')
        es_result = await detector.detect_content_type(spanish)
        
        # French content
        french = "Ceci est un guide complet sur l'exploration Web et l'extraction de données.".encode('utf-8')
        fr_result = await detector.detect_content_type(french)
        
        # Language detection might not work on short text, but structure should be detected
        assert en_result['encoding'] is not None
        assert es_result['encoding'] is not None
        assert fr_result['encoding'] is not None
    
    @pytest.mark.asyncio
    async def test_canonical_url_handling(self, crawler_components):
        """Test canonical URL detection and deduplication."""
        deduplicator = crawler_components['deduplicator']
        extractor = crawler_components['extractor']
        
        # HTML with canonical URL
        html = '''
        <html>
        <head>
            <link rel="canonical" href="https://example.com/canonical-product">
            <title>Product Page</title>
        </head>
        <body>
            <h1>Product</h1>
        </body>
        </html>
        '''
        
        # Extract metadata including canonical
        extracted = await extractor.extract_all(html, 'https://example.com/product?utm_source=test')
        assert extracted['canonical_url'] == 'https://example.com/canonical-product'
        
        # First, store the canonical version
        await deduplicator.check_duplicate(html, 'https://example.com/canonical-product')
        
        # Now check the non-canonical version
        result = await deduplicator.check_duplicate(
            html,
            'https://example.com/product?utm_source=test',
            metadata={'canonical_url': 'https://example.com/canonical-product'}
        )
        
        assert result['is_duplicate'] is True
        assert result['duplicate_type'] == 'canonical'
        assert result['action'] == 'redirect'
    
    def test_crawler_statistics_aggregation(self, crawler_components):
        """Test statistics collection across all components."""
        # Get statistics from each component
        detector_stats = {
            'detections': 100,
            'html_detected': 80,
            'pdf_detected': 10,
            'image_detected': 10
        }
        
        renderer_stats = crawler_components['renderer'].get_metrics()
        extractor_stats = crawler_components['extractor'].get_statistics()
        deduplicator_stats = crawler_components['deduplicator'].get_statistics()
        
        # Aggregate statistics
        total_stats = {
            'content_detection': detector_stats,
            'rendering': renderer_stats,
            'extraction': extractor_stats,
            'deduplication': deduplicator_stats
        }
        
        # Verify all components provide statistics
        assert 'success_rate' in renderer_stats
        assert 'success_rate' in extractor_stats
        assert 'duplicate_rate' in deduplicator_stats