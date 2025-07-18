"""Test script for enhanced crawler functionality."""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

from src.crawler.enhanced_crawler import EnhancedWebCrawler, DuplicationPolicy
from src.rendering import RenderingOptions, WaitStrategy


async def test_content_detection():
    """Test content type detection."""
    print("\n=== Testing Content Type Detection ===")
    
    crawler = EnhancedWebCrawler(
        enable_javascript=False,
        enable_deduplication=False,
        enable_content_analysis=True,
        enable_structured_extraction=False
    )
    
    async with crawler:
        # Test various content types
        test_urls = [
            "https://example.com",
            "https://www.python.org",
            "https://api.github.com"
        ]
        
        for url in test_urls:
            print(f"\nCrawling: {url}")
            result = await crawler.crawl(url)
            
            if result.content_detection:
                print(f"  MIME Type: {result.content_detection['mime_type']}")
                print(f"  Encoding: {result.content_detection['encoding']}")
                print(f"  Language: {result.content_detection['language']}")
                print(f"  Structure: {result.content_detection['structure']}")
                print(f"  Confidence: {result.content_detection['confidence']}")
            else:
                print(f"  Error: {result.error}")


async def test_javascript_rendering():
    """Test JavaScript rendering capabilities."""
    print("\n=== Testing JavaScript Rendering ===")
    
    crawler = EnhancedWebCrawler(
        enable_javascript=True,
        enable_deduplication=False,
        enable_content_analysis=False,
        enable_structured_extraction=False,
        browser_pool_size=2
    )
    
    async with crawler:
        # Test SPA sites
        test_urls = [
            "https://angular.io",
            "https://reactjs.org"
        ]
        
        for url in test_urls:
            print(f"\nRendering: {url}")
            
            # First without JS
            print("  Without JavaScript:")
            result_no_js = await crawler.crawl(url, render_javascript=False)
            print(f"    Content length: {len(result_no_js.content) if result_no_js.content else 0}")
            print(f"    Links found: {len(result_no_js.links)}")
            
            # Then with JS
            print("  With JavaScript:")
            result_js = await crawler.crawl(url, render_javascript=True)
            print(f"    Content length: {len(result_js.content) if result_js.content else 0}")
            print(f"    Links found: {len(result_js.links)}")
            print(f"    JS rendered: {result_js.javascript_rendered}")
            print(f"    Render time: {result_js.processing_time.get('js_rendering', 0):.2f}s")


async def test_structured_extraction():
    """Test structured data extraction."""
    print("\n=== Testing Structured Data Extraction ===")
    
    crawler = EnhancedWebCrawler(
        enable_javascript=False,
        enable_deduplication=False,
        enable_content_analysis=False,
        enable_structured_extraction=True
    )
    
    async with crawler:
        # Test sites with structured data
        test_urls = [
            "https://schema.org",
            "https://www.imdb.com",
            "https://en.wikipedia.org/wiki/Python_(programming_language)"
        ]
        
        for url in test_urls:
            print(f"\nExtracting from: {url}")
            result = await crawler.crawl(url)
            
            if result.structured_data:
                data = result.structured_data
                
                # JSON-LD
                if data['structured_data'].get('json_ld'):
                    print(f"  JSON-LD found: {len(data['structured_data']['json_ld'])} items")
                    for item in data['structured_data']['json_ld'][:2]:
                        print(f"    - Type: {item.get('type')}")
                        print(f"      Name: {item.get('name', 'N/A')}")
                
                # OpenGraph
                if data['structured_data'].get('opengraph'):
                    print("  OpenGraph data:")
                    og = data['structured_data']['opengraph']
                    print(f"    Title: {og.get('title', 'N/A')}")
                    print(f"    Type: {og.get('type', 'N/A')}")
                    print(f"    URL: {og.get('url', 'N/A')}")
                
                # Metadata
                if data.get('metadata'):
                    print("  Metadata:")
                    meta = data['metadata']
                    print(f"    Title: {meta.get('title', 'N/A')}")
                    print(f"    Description: {meta.get('description', 'N/A')[:100]}...")
                    print(f"    Keywords: {len(meta.get('keywords', []))} found")
                
                # Entities
                if data.get('entities'):
                    print(f"  Entities found: {len(data['entities'])}")
                    for entity in data['entities'][:3]:
                        print(f"    - {entity.get('category')}: {entity.get('name', 'N/A')}")


async def test_content_filtering():
    """Test main content extraction and filtering."""
    print("\n=== Testing Content Filtering ===")
    
    crawler = EnhancedWebCrawler(
        enable_javascript=False,
        enable_deduplication=False,
        enable_content_analysis=True,
        enable_structured_extraction=False
    )
    
    async with crawler:
        # Test news/article sites
        test_urls = [
            "https://en.wikipedia.org/wiki/Web_crawler",
            "https://www.python.org/about/"
        ]
        
        for url in test_urls:
            print(f"\nFiltering content from: {url}")
            result = await crawler.crawl(url)
            
            if result.main_content:
                main = result.main_content['main_content']
                print(f"  Original content length: {result.content_length}")
                print(f"  Main content length: {main['char_count']}")
                print(f"  Word count: {main['word_count']}")
                
                structure = main['structure']
                print(f"  Structure:")
                print(f"    Headings: {len(structure['headings'])}")
                print(f"    Paragraphs: {len(structure['paragraphs'])}")
                print(f"    Images: {len(structure['images'])}")
                print(f"    Lists: {len(structure['lists'])}")
                
                # Show first paragraph
                if structure['paragraphs']:
                    print(f"  First paragraph: {structure['paragraphs'][0][:150]}...")
            
            # Content analysis
            if result.content_analysis:
                analysis = result.content_analysis
                if 'quality' in analysis:
                    print(f"  Content quality score: {analysis['quality']['score']}/100")
                    print(f"  Quality factors: {', '.join(analysis['quality']['factors'])}")
                
                if 'keywords' in analysis:
                    top_keywords = analysis['keywords'][:5]
                    print(f"  Top keywords: {', '.join(k['keyword'] for k in top_keywords)}")


async def test_deduplication():
    """Test content deduplication."""
    print("\n=== Testing Content Deduplication ===")
    
    policy = DuplicationPolicy(
        exact_match_threshold=0.95,
        near_duplicate_threshold=0.80,
        reject_exact_duplicates=True,
        reject_near_duplicates=True
    )
    
    crawler = EnhancedWebCrawler(
        enable_javascript=False,
        enable_deduplication=True,
        enable_content_analysis=False,
        enable_structured_extraction=False,
        deduplication_policy=policy
    )
    
    async with crawler:
        # Test with same content from different URLs
        test_urls = [
            "https://example.com",
            "https://example.com/",  # Same with trailing slash
            "http://example.com",    # HTTP version
            "https://www.example.com" # www version
        ]
        
        for i, url in enumerate(test_urls):
            print(f"\nChecking: {url}")
            result = await crawler.crawl(url)
            
            if result.duplication_check:
                dup = result.duplication_check
                print(f"  Is duplicate: {dup['is_duplicate']}")
                print(f"  Duplicate type: {dup.get('duplicate_type', 'N/A')}")
                print(f"  Action: {dup['action']}")
                
                if dup['is_duplicate']:
                    print(f"  Original URL: {dup.get('original_url', 'N/A')}")
                    print(f"  Similarity score: {dup.get('similarity_score', 0):.2f}")
                
                # Show fingerprint
                if 'fingerprint' in dup:
                    fp = dup['fingerprint']
                    print(f"  Fingerprint:")
                    print(f"    SHA256: {fp['sha256'][:16]}...")
                    print(f"    SimHash: {fp['simhash']}")
                    print(f"    Word count: {fp['word_count']}")


async def test_custom_extraction():
    """Test custom extraction rules."""
    print("\n=== Testing Custom Extraction Rules ===")
    
    crawler = EnhancedWebCrawler(
        enable_javascript=False,
        enable_deduplication=False,
        enable_content_analysis=False,
        enable_structured_extraction=False
    )
    
    async with crawler:
        # Test e-commerce site
        url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
        print(f"\nExtracting product data from: {url}")
        
        result = await crawler.crawl(url, extraction_rules='product')
        
        if hasattr(result, 'custom_extractions') and 'product' in result.custom_extractions:
            product = result.custom_extractions['product']
            print("  Product data:")
            for key, value in product.items():
                if value is not None:
                    print(f"    {key}: {value}")


async def test_batch_crawling():
    """Test batch crawling with full processing."""
    print("\n=== Testing Batch Crawling ===")
    
    crawler = EnhancedWebCrawler(
        enable_javascript=False,
        enable_deduplication=True,
        enable_content_analysis=True,
        enable_structured_extraction=True
    )
    
    async with crawler:
        urls = [
            "https://www.python.org",
            "https://docs.python.org",
            "https://pypi.org"
        ]
        
        print(f"Crawling {len(urls)} URLs in batch...")
        start_time = asyncio.get_event_loop().time()
        
        results = await crawler.crawl_batch(urls)
        
        total_time = asyncio.get_event_loop().time() - start_time
        print(f"\nCompleted in {total_time:.2f}s")
        
        for result in results:
            print(f"\n{result.url}:")
            print(f"  Status: {result.status_code}")
            print(f"  Content type: {result.content_detection['mime_type'] if result.content_detection else 'N/A'}")
            print(f"  Language: {result.content_detection.get('language', 'N/A') if result.content_detection else 'N/A'}")
            print(f"  Is duplicate: {result.duplication_check['is_duplicate'] if result.duplication_check else 'N/A'}")
            print(f"  Processing times:")
            for step, time_taken in result.processing_time.items():
                if step != 'total':
                    print(f"    {step}: {time_taken:.3f}s")
        
        # Show statistics
        print("\n=== Crawler Statistics ===")
        stats = crawler.get_statistics()
        print(json.dumps(stats, indent=2))


async def main():
    """Run all tests."""
    tests = [
        test_content_detection,
        test_javascript_rendering,
        test_structured_extraction,
        test_content_filtering,
        test_deduplication,
        test_custom_extraction,
        test_batch_crawling
    ]
    
    for test in tests:
        try:
            await test()
        except Exception as e:
            print(f"\nError in {test.__name__}: {e}")
        
        # Small delay between tests
        await asyncio.sleep(1)


if __name__ == "__main__":
    print("Enhanced Crawler Test Suite")
    print("==========================")
    asyncio.run(main())