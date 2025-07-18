"""Demonstration of the complete crawler system with all advanced features."""

import asyncio
import json
from typing import Dict, Any
from datetime import datetime

from content.detector import ContentDetector
from rendering.renderer import JavaScriptRenderer
from rendering.browser_pool import BrowserPool
from rendering.strategies import RenderingOptions, WaitStrategy
from extraction.extractor import StructuredDataExtractor
from deduplication.deduplicator import ContentDeduplicator, DuplicationPolicy

import structlog

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
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class AdvancedWebCrawler:
    """Complete web crawler with all advanced features integrated."""
    
    def __init__(self):
        """Initialize all crawler components."""
        self.browser_pool = BrowserPool(max_browsers=3)
        self.content_detector = ContentDetector()
        self.renderer = JavaScriptRenderer(self.browser_pool)
        self.extractor = StructuredDataExtractor()
        self.deduplicator = ContentDeduplicator(
            policy=DuplicationPolicy(
                reject_exact_duplicates=True,
                reject_near_duplicates=True,
                prefer_canonical=True
            )
        )
        
        self.crawl_stats = {
            'urls_processed': 0,
            'successful_crawls': 0,
            'failed_crawls': 0,
            'duplicates_found': 0,
            'unique_content': 0,
            'start_time': datetime.utcnow()
        }
    
    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """
        Crawl a single URL with full pipeline processing.
        
        Args:
            url: URL to crawl
            
        Returns:
            Complete crawl results including rendered content, 
            detected type, extracted data, and deduplication status
        """
        logger.info(f"Starting crawl", url=url)
        self.crawl_stats['urls_processed'] += 1
        
        result = {
            'url': url,
            'timestamp': datetime.utcnow().isoformat(),
            'success': False,
            'error': None,
            'rendering': None,
            'content_type': None,
            'structured_data': None,
            'deduplication': None
        }
        
        try:
            # Step 1: Render the page with JavaScript
            logger.info("Rendering page with JavaScript")
            render_options = RenderingOptions(
                wait_strategy=WaitStrategy.NETWORKIDLE,
                timeout=30000,
                take_screenshot=True,
                screenshot_full_page=False,
                extract_resources=True,
                extract_network_logs=True,
                extract_console_logs=True,
                block_resources=['font', 'media'],
                intercept_ajax=True
            )
            
            render_result = await self.renderer.render_page(url, render_options)
            
            if not render_result['success']:
                raise Exception(f"Rendering failed: {render_result.get('error', 'Unknown error')}")
            
            result['rendering'] = {
                'title': render_result['title'],
                'final_url': render_result['url'],
                'render_time': render_result['render_time'],
                'has_screenshot': bool(render_result.get('screenshot')),
                'resources_count': len(render_result.get('resources', [])),
                'console_errors': sum(1 for log in render_result.get('console_logs', []) 
                                    if log.get('type') == 'error')
            }
            
            # Step 2: Detect content type and encoding
            logger.info("Detecting content type and encoding")
            content_bytes = render_result['html'].encode('utf-8')
            
            content_type = await self.content_detector.detect_content_type(
                content_bytes,
                url=url,
                headers=render_result.get('metadata', {}).get('headers', {})
            )
            
            result['content_type'] = {
                'mime_type': content_type['mime_type'],
                'encoding': content_type['encoding'],
                'language': content_type['language'],
                'structure': content_type['structure'],
                'confidence': content_type['confidence']
            }
            
            # Step 3: Extract structured data
            logger.info("Extracting structured data")
            extracted_data = await self.extractor.extract_all(
                render_result['html'],
                render_result['url']  # Use final URL after redirects
            )
            
            result['structured_data'] = {
                'has_json_ld': bool(extracted_data['structured_data'].get('json_ld')),
                'has_microdata': bool(extracted_data['structured_data'].get('microdata')),
                'has_opengraph': bool(extracted_data['structured_data'].get('opengraph')),
                'has_twitter_card': bool(extracted_data['structured_data'].get('twitter_card')),
                'canonical_url': extracted_data['canonical_url'],
                'entities_found': len(extracted_data['entities']),
                'social_profiles': extracted_data['social_profiles'],
                'metadata': extracted_data['metadata']
            }
            
            # Include actual structured data for demo
            if extracted_data['structured_data'].get('json_ld'):
                result['structured_data']['json_ld_sample'] = extracted_data['structured_data']['json_ld'][:2]
            
            # Step 4: Check for duplicates
            logger.info("Checking for duplicate content")
            dup_result = await self.deduplicator.check_duplicate(
                render_result['html'],
                render_result['url'],
                metadata=extracted_data
            )
            
            result['deduplication'] = {
                'is_duplicate': dup_result['is_duplicate'],
                'duplicate_type': dup_result['duplicate_type'],
                'action': dup_result['action'],
                'original_url': dup_result.get('original_url'),
                'similarity_score': dup_result.get('similarity_score'),
                'content_hash': dup_result['fingerprint']['sha256'][:16] + '...'
            }
            
            if dup_result['is_duplicate']:
                self.crawl_stats['duplicates_found'] += 1
            else:
                self.crawl_stats['unique_content'] += 1
            
            # Mark as successful
            result['success'] = True
            self.crawl_stats['successful_crawls'] += 1
            
            logger.info("Crawl completed successfully", 
                       is_duplicate=dup_result['is_duplicate'],
                       content_type=content_type['mime_type'])
            
        except Exception as e:
            logger.error(f"Crawl failed", url=url, error=str(e))
            result['error'] = str(e)
            self.crawl_stats['failed_crawls'] += 1
        
        return result
    
    async def crawl_multiple_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs concurrently.
        
        Args:
            urls: List of URLs to crawl
            
        Returns:
            List of crawl results
        """
        logger.info(f"Starting batch crawl", url_count=len(urls))
        
        # Crawl URLs concurrently but with a limit
        results = []
        batch_size = 3
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self.crawl_url(url) for url in batch],
                return_exceptions=True
            )
            
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results.append({
                        'url': url,
                        'success': False,
                        'error': str(result)
                    })
                else:
                    results.append(result)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive crawler statistics."""
        runtime = (datetime.utcnow() - self.crawl_stats['start_time']).total_seconds()
        
        return {
            'crawl_stats': {
                **self.crawl_stats,
                'runtime_seconds': runtime,
                'urls_per_minute': (self.crawl_stats['urls_processed'] / runtime * 60) if runtime > 0 else 0,
                'success_rate': (self.crawl_stats['successful_crawls'] / 
                               max(self.crawl_stats['urls_processed'], 1)),
                'duplicate_rate': (self.crawl_stats['duplicates_found'] / 
                                 max(self.crawl_stats['successful_crawls'], 1))
            },
            'component_stats': {
                'renderer': self.renderer.get_metrics(),
                'extractor': self.extractor.get_statistics(),
                'deduplicator': self.deduplicator.get_statistics()
            }
        }
    
    async def close(self):
        """Clean up resources."""
        await self.browser_pool.close()
        await self.deduplicator.clear_cache()


async def main():
    """Run crawler demonstration."""
    crawler = AdvancedWebCrawler()
    
    try:
        # Example URLs to crawl
        test_urls = [
            "https://example.com",
            "https://www.wikipedia.org",
            "https://httpbin.org/html",
            "https://example.com",  # Duplicate of first URL
            "https://httpbin.org/delay/2"  # Slow loading page
        ]
        
        print("=" * 80)
        print("Advanced Web Crawler Demonstration")
        print("=" * 80)
        
        # Crawl URLs
        results = await crawler.crawl_multiple_urls(test_urls)
        
        # Display results
        for result in results:
            print(f"\nURL: {result['url']}")
            print(f"Success: {result['success']}")
            
            if result['success']:
                print(f"Content Type: {result['content_type']['mime_type']} "
                      f"(confidence: {result['content_type']['confidence']})")
                print(f"Language: {result['content_type']['language']}")
                print(f"Encoding: {result['content_type']['encoding']}")
                print(f"Structure: {result['content_type']['structure']}")
                
                print(f"\nRendering:")
                print(f"  Title: {result['rendering']['title']}")
                print(f"  Render Time: {result['rendering']['render_time']:.2f}s")
                print(f"  Resources: {result['rendering']['resources_count']}")
                print(f"  Console Errors: {result['rendering']['console_errors']}")
                
                print(f"\nStructured Data:")
                print(f"  JSON-LD: {result['structured_data']['has_json_ld']}")
                print(f"  Microdata: {result['structured_data']['has_microdata']}")
                print(f"  OpenGraph: {result['structured_data']['has_opengraph']}")
                print(f"  Entities Found: {result['structured_data']['entities_found']}")
                print(f"  Canonical URL: {result['structured_data']['canonical_url']}")
                
                print(f"\nDeduplication:")
                print(f"  Is Duplicate: {result['deduplication']['is_duplicate']}")
                if result['deduplication']['is_duplicate']:
                    print(f"  Type: {result['deduplication']['duplicate_type']}")
                    print(f"  Original URL: {result['deduplication']['original_url']}")
                    print(f"  Similarity: {result['deduplication'].get('similarity_score', 'N/A')}")
                print(f"  Content Hash: {result['deduplication']['content_hash']}")
            else:
                print(f"Error: {result['error']}")
        
        # Display statistics
        print("\n" + "=" * 80)
        print("Crawler Statistics")
        print("=" * 80)
        
        stats = crawler.get_statistics()
        crawl_stats = stats['crawl_stats']
        
        print(f"\nCrawl Summary:")
        print(f"  URLs Processed: {crawl_stats['urls_processed']}")
        print(f"  Successful: {crawl_stats['successful_crawls']}")
        print(f"  Failed: {crawl_stats['failed_crawls']}")
        print(f"  Duplicates Found: {crawl_stats['duplicates_found']}")
        print(f"  Unique Content: {crawl_stats['unique_content']}")
        print(f"  Success Rate: {crawl_stats['success_rate']:.1%}")
        print(f"  Duplicate Rate: {crawl_stats['duplicate_rate']:.1%}")
        print(f"  Runtime: {crawl_stats['runtime_seconds']:.1f}s")
        print(f"  Speed: {crawl_stats['urls_per_minute']:.1f} URLs/minute")
        
        print(f"\nRenderer Metrics:")
        renderer_stats = stats['component_stats']['renderer']
        print(f"  Average Render Time: {renderer_stats['average_render_time']:.2f}s")
        print(f"  Success Rate: {renderer_stats['success_rate']:.1%}")
        print(f"  Timeout Errors: {renderer_stats['timeout_errors']}")
        
        print(f"\nExtractor Statistics:")
        extractor_stats = stats['component_stats']['extractor']
        print(f"  Total Extractions: {extractor_stats['total_extractions']}")
        print(f"  JSON-LD Found: {extractor_stats['json_ld_found']}")
        print(f"  OpenGraph Found: {extractor_stats['opengraph_found']}")
        
        print(f"\nDeduplicator Statistics:")
        dedup_stats = stats['component_stats']['deduplicator']
        print(f"  Total Checked: {dedup_stats['total_checked']}")
        print(f"  Exact Duplicates: {dedup_stats['exact_duplicates']}")
        print(f"  Near Duplicates: {dedup_stats['near_duplicates']}")
        print(f"  Similar Content: {dedup_stats['similar_content']}")
        
    finally:
        await crawler.close()
        print("\nCrawler shutdown complete.")


if __name__ == "__main__":
    # Note: This requires actual browser installation for Playwright
    # Run: playwright install chromium
    asyncio.run(main())