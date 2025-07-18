"""Tests for structured data extraction module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from extraction.extractor import StructuredDataExtractor


class TestStructuredDataExtractor:
    """Test cases for StructuredDataExtractor class."""
    
    @pytest.fixture
    def extractor(self):
        """Create StructuredDataExtractor instance."""
        return StructuredDataExtractor()
    
    @pytest.fixture
    def sample_html_with_json_ld(self):
        """Sample HTML with JSON-LD structured data."""
        return '''<!DOCTYPE html>
        <html>
        <head>
            <title>Test Product Page</title>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": "Test Product",
                "description": "A test product description",
                "image": "https://example.com/product.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "99.99",
                    "priceCurrency": "USD"
                }
            }
            </script>
        </head>
        <body>
            <h1>Test Product</h1>
        </body>
        </html>'''
    
    @pytest.fixture
    def sample_html_with_microdata(self):
        """Sample HTML with Microdata."""
        return '''<!DOCTYPE html>
        <html>
        <body>
            <div itemscope itemtype="https://schema.org/Person">
                <span itemprop="name">John Doe</span>
                <span itemprop="jobTitle">Software Engineer</span>
                <a itemprop="url" href="https://johndoe.com">Website</a>
            </div>
        </body>
        </html>'''
    
    @pytest.fixture
    def sample_html_with_opengraph(self):
        """Sample HTML with OpenGraph metadata."""
        return '''<!DOCTYPE html>
        <html>
        <head>
            <meta property="og:title" content="Test Article">
            <meta property="og:description" content="This is a test article">
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:url" content="https://example.com/article">
            <meta property="og:type" content="article">
        </head>
        <body>
            <h1>Test Article</h1>
        </body>
        </html>'''
    
    @pytest.fixture
    def sample_html_with_twitter_card(self):
        """Sample HTML with Twitter Card metadata."""
        return '''<!DOCTYPE html>
        <html>
        <head>
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:title" content="Test Tweet">
            <meta name="twitter:description" content="Test tweet description">
            <meta name="twitter:image" content="https://example.com/twitter.jpg">
            <meta name="twitter:site" content="@testsite">
        </head>
        <body>
            <h1>Test Page</h1>
        </body>
        </html>'''
    
    @pytest.mark.asyncio
    @patch('extruct.extract')
    async def test_extract_json_ld(self, mock_extract, extractor, sample_html_with_json_ld):
        """Test JSON-LD extraction."""
        mock_extract.return_value = {
            'json-ld': [{
                '@context': 'https://schema.org/',
                '@type': 'Product',
                'name': 'Test Product',
                'description': 'A test product description',
                'offers': {
                    '@type': 'Offer',
                    'price': '99.99',
                    'priceCurrency': 'USD'
                }
            }]
        }
        
        result = await extractor.extract_all(sample_html_with_json_ld, 'https://example.com')
        
        assert 'json_ld' in result['structured_data']
        assert len(result['structured_data']['json_ld']) == 1
        assert result['structured_data']['json_ld'][0]['type'] == 'Product'
        assert result['structured_data']['json_ld'][0]['name'] == 'Test Product'
        assert extractor.extraction_stats['json_ld_found'] == 1
    
    @pytest.mark.asyncio
    @patch('extruct.extract')
    async def test_extract_microdata(self, mock_extract, extractor, sample_html_with_microdata):
        """Test Microdata extraction."""
        mock_extract.return_value = {
            'microdata': [{
                'type': ['https://schema.org/Person'],
                'properties': {
                    'name': 'John Doe',
                    'jobTitle': 'Software Engineer',
                    'url': 'https://johndoe.com'
                }
            }]
        }
        
        result = await extractor.extract_all(sample_html_with_microdata, 'https://example.com')
        
        assert 'microdata' in result['structured_data']
        assert len(result['structured_data']['microdata']) == 1
        assert result['structured_data']['microdata'][0]['type'] == 'https://schema.org/Person'
        assert extractor.extraction_stats['microdata_found'] == 1
    
    @pytest.mark.asyncio
    @patch('extruct.extract')
    async def test_extract_opengraph(self, mock_extract, extractor, sample_html_with_opengraph):
        """Test OpenGraph extraction."""
        mock_extract.return_value = {
            'opengraph': [{
                'og:title': 'Test Article',
                'og:description': 'This is a test article',
                'og:image': 'https://example.com/image.jpg',
                'og:url': 'https://example.com/article',
                'og:type': 'article'
            }]
        }
        
        result = await extractor.extract_all(sample_html_with_opengraph, 'https://example.com')
        
        assert 'opengraph' in result['structured_data']
        og_data = result['structured_data']['opengraph']
        assert og_data['title'] == 'Test Article'
        assert og_data['description'] == 'This is a test article'
        assert extractor.extraction_stats['opengraph_found'] == 1
    
    @pytest.mark.asyncio
    async def test_extract_twitter_card(self, extractor, sample_html_with_twitter_card):
        """Test Twitter Card extraction."""
        result = await extractor.extract_all(sample_html_with_twitter_card, 'https://example.com')
        
        assert 'twitter_card' in result['structured_data']
        twitter_data = result['structured_data']['twitter_card']
        assert twitter_data['card'] == 'summary_large_image'
        assert twitter_data['title'] == 'Test Tweet'
        assert twitter_data['site'] == '@testsite'
        assert extractor.extraction_stats['twitter_found'] == 1
    
    @pytest.mark.asyncio
    async def test_extract_canonical_url(self, extractor):
        """Test canonical URL extraction."""
        html_with_canonical = '''<!DOCTYPE html>
        <html>
        <head>
            <link rel="canonical" href="https://example.com/canonical-page">
        </head>
        <body></body>
        </html>'''
        
        result = await extractor.extract_all(html_with_canonical, 'https://example.com/page')
        
        assert result['canonical_url'] == 'https://example.com/canonical-page'
    
    @pytest.mark.asyncio
    async def test_extract_canonical_url_from_opengraph(self, extractor):
        """Test canonical URL extraction from OpenGraph as fallback."""
        html_with_og_url = '''<!DOCTYPE html>
        <html>
        <head>
            <meta property="og:url" content="https://example.com/og-canonical">
        </head>
        <body></body>
        </html>'''
        
        result = await extractor.extract_all(html_with_og_url, 'https://example.com/page')
        
        assert result['canonical_url'] == 'https://example.com/og-canonical'
    
    @pytest.mark.asyncio
    async def test_extract_alternate_urls(self, extractor):
        """Test alternate URL extraction."""
        html_with_alternates = '''<!DOCTYPE html>
        <html>
        <head>
            <link rel="alternate" hreflang="en" href="https://example.com/en/page">
            <link rel="alternate" hreflang="es" href="https://example.com/es/page">
            <link rel="alternate" type="application/rss+xml" href="/feed.xml">
        </head>
        <body></body>
        </html>'''
        
        result = await extractor.extract_all(html_with_alternates, 'https://example.com')
        
        assert len(result['alternate_urls']) == 3
        assert any(alt['hreflang'] == 'en' for alt in result['alternate_urls'])
        assert any(alt['hreflang'] == 'es' for alt in result['alternate_urls'])
        assert any(alt['type'] == 'application/rss+xml' for alt in result['alternate_urls'])
    
    @pytest.mark.asyncio
    async def test_extract_metadata(self, extractor):
        """Test general metadata extraction."""
        html_with_metadata = '''<!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Test Page Title</title>
            <meta name="description" content="Test page description">
            <meta name="keywords" content="test, page, keywords">
            <meta name="author" content="Test Author">
            <meta name="robots" content="index, follow">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="icon" href="/favicon.ico">
            <link rel="alternate" type="application/rss+xml" title="RSS Feed" href="/rss.xml">
        </head>
        <body></body>
        </html>'''
        
        result = await extractor.extract_all(html_with_metadata, 'https://example.com')
        
        metadata = result['metadata']
        assert metadata['title'] == 'Test Page Title'
        assert metadata['description'] == 'Test page description'
        assert metadata['keywords'] == ['test', 'page', 'keywords']
        assert metadata['author'] == 'Test Author'
        assert metadata['robots'] == 'index, follow'
        assert metadata['viewport'] == 'width=device-width, initial-scale=1.0'
        assert metadata['language'] == 'en'
        assert metadata['favicon'] == 'https://example.com/favicon.ico'
        assert len(metadata['rss_feeds']) == 1
    
    @pytest.mark.asyncio
    async def test_extract_entities(self, extractor):
        """Test entity extraction from structured data."""
        structured_data = {
            'json_ld': [
                {
                    'type': 'Person',
                    'name': 'John Doe',
                    'description': 'A person',
                    'url': 'https://johndoe.com',
                    'jobTitle': 'Engineer'
                },
                {
                    'type': 'Article',
                    'name': 'Test Article',
                    'description': 'An article',
                    'url': 'https://example.com/article'
                }
            ]
        }
        
        entities = extractor._extract_entities(structured_data)
        
        assert len(entities) == 2
        assert entities[0]['category'] == 'person'
        assert entities[0]['name'] == 'John Doe'
        assert entities[1]['category'] == 'article'
        assert entities[1]['name'] == 'Test Article'
    
    @pytest.mark.asyncio
    async def test_extract_social_profiles(self, extractor):
        """Test social profile extraction."""
        html_with_social = '''<!DOCTYPE html>
        <html>
        <body>
            <a href="https://facebook.com/testpage">Facebook</a>
            <a href="https://twitter.com/testuser">Twitter</a>
            <a href="https://linkedin.com/company/testcompany">LinkedIn</a>
            <a href="https://github.com/testuser">GitHub</a>
        </body>
        </html>'''
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_with_social, 'lxml')
        
        social_profiles = extractor._extract_social_profiles(soup, {})
        
        assert len(social_profiles) == 4
        platforms = [profile['platform'] for profile in social_profiles]
        assert 'facebook' in platforms
        assert 'twitter' in platforms
        assert 'linkedin' in platforms
        assert 'github' in platforms
    
    @pytest.mark.asyncio
    async def test_process_json_ld_with_graph(self, extractor):
        """Test processing JSON-LD with @graph structure."""
        json_ld_data = [{
            '@graph': [
                {'@type': 'WebSite', 'name': 'Test Site'},
                {'@type': 'WebPage', 'name': 'Test Page'}
            ]
        }]
        
        processed = extractor._process_json_ld(json_ld_data)
        
        assert len(processed) == 2
        assert processed[0]['type'] == 'WebSite'
        assert processed[1]['type'] == 'WebPage'
    
    def test_normalize_json_ld_item(self, extractor):
        """Test JSON-LD item normalization."""
        item = {
            '@type': 'Product',
            'name': 'Test Product',
            'price': {'@value': '99.99'},
            '@id': 'product-123'
        }
        
        normalized = extractor._normalize_json_ld_item(item)
        
        assert normalized['type'] == 'Product'
        assert normalized['name'] == 'Test Product'
        assert normalized['price'] == '99.99'
        assert '@id' not in normalized
    
    @pytest.mark.asyncio
    @patch('extruct.extract')
    async def test_extract_with_error_handling(self, mock_extract, extractor):
        """Test extraction with error handling."""
        mock_extract.side_effect = Exception("Extraction error")
        
        html = '<html><body>Test</body></html>'
        result = await extractor.extract_all(html, 'https://example.com')
        
        # Should still return a valid result structure
        assert 'structured_data' in result
        assert 'metadata' in result
        assert result['url'] == 'https://example.com'
    
    def test_get_statistics(self, extractor):
        """Test statistics retrieval."""
        extractor.extraction_stats = {
            'total_extractions': 100,
            'json_ld_found': 50,
            'microdata_found': 30,
            'rdfa_found': 10,
            'opengraph_found': 80,
            'twitter_found': 70
        }
        
        stats = extractor.get_statistics()
        
        assert stats['total_extractions'] == 100
        assert stats['success_rate']['json_ld'] == 0.5
        assert stats['success_rate']['microdata'] == 0.3
        assert stats['success_rate']['opengraph'] == 0.8
    
    @pytest.mark.asyncio
    async def test_extract_social_profiles_from_structured_data(self, extractor):
        """Test social profile extraction from structured data."""
        structured_data = {
            'json_ld': [{
                'sameAs': [
                    'https://facebook.com/company',
                    'https://twitter.com/company',
                    'https://linkedin.com/company/ourcompany'
                ]
            }]
        }
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup('<html></html>', 'lxml')
        
        social_profiles = extractor._extract_social_profiles(soup, structured_data)
        
        assert len(social_profiles) == 3
        assert all(profile['source'] == 'structured_data' for profile in social_profiles)