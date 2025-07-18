"""Core web crawler implementation"""

import asyncio
import hashlib
import time
from typing import Optional, List, Dict, Set, Tuple
from datetime import datetime
from urllib.parse import urlparse, urljoin, urldefrag
from dataclasses import dataclass, field

import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from bs4 import BeautifulSoup
import structlog
from yarl import URL

logger = structlog.get_logger(__name__)


@dataclass
class CrawlResult:
    """Result of crawling a single URL"""
    url: str
    status_code: int
    content: Optional[str] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    title: Optional[str] = None
    meta_description: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    crawl_time: float = 0.0
    error: Optional[str] = None
    redirect_chain: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "url": self.url,
            "status_code": self.status_code,
            "content": self.content,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "links": self.links,
            "images": self.images,
            "title": self.title,
            "meta_description": self.meta_description,
            "headers": self.headers,
            "crawl_time": self.crawl_time,
            "error": self.error,
            "redirect_chain": self.redirect_chain,
            "timestamp": datetime.utcnow().isoformat()
        }


class WebCrawler:
    """
    Async web crawler with advanced features:
    - Connection pooling
    - Retry logic
    - Content extraction
    - Link discovery
    - Error handling
    """
    
    def __init__(
        self,
        user_agent: str = "LLMOptimizer/1.0",
        timeout: float = 30.0,
        max_content_length: int = 10_000_000,  # 10MB
        max_redirects: int = 5,
        concurrent_requests: int = 10,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        allowed_content_types: Optional[Set[str]] = None
    ):
        self.user_agent = user_agent
        self.timeout = ClientTimeout(total=timeout)
        self.max_content_length = max_content_length
        self.max_redirects = max_redirects
        self.concurrent_requests = concurrent_requests
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        # Default allowed content types
        self.allowed_content_types = allowed_content_types or {
            "text/html",
            "application/xhtml+xml",
            "text/xml",
            "application/xml"
        }
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(concurrent_requests)
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def start(self):
        """Initialize crawler session"""
        if not self._session:
            connector = TCPConnector(
                limit=100,
                limit_per_host=10,
                ttl_dns_cache=300
            )
            
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=headers
            )
            
            logger.info("Web crawler started")
            
    async def close(self):
        """Close crawler session"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("Web crawler closed")
            
    async def crawl(self, url: str) -> CrawlResult:
        """Crawl a single URL"""
        if not self._session:
            await self.start()
            
        async with self._semaphore:
            return await self._crawl_with_retry(url)
            
    async def _crawl_with_retry(self, url: str) -> CrawlResult:
        """Crawl with retry logic"""
        last_error = None
        
        for attempt in range(self.retry_attempts):
            try:
                return await self._crawl_url(url)
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Crawl attempt failed",
                    url=url,
                    attempt=attempt + 1,
                    error=last_error
                )
                
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    
        # All attempts failed
        return CrawlResult(
            url=url,
            status_code=0,
            error=f"Failed after {self.retry_attempts} attempts: {last_error}"
        )
        
    async def _crawl_url(self, url: str) -> CrawlResult:
        """Perform actual crawl"""
        start_time = time.time()
        redirect_chain = []
        
        try:
            async with self._session.get(
                url,
                allow_redirects=False,
                max_redirects=0
            ) as response:
                # Handle redirects manually to track chain
                current_url = url
                current_response = response
                
                while current_response.status in (301, 302, 303, 307, 308):
                    redirect_chain.append(current_url)
                    
                    if len(redirect_chain) > self.max_redirects:
                        raise Exception(f"Too many redirects (>{self.max_redirects})")
                        
                    location = current_response.headers.get("Location")
                    if not location:
                        break
                        
                    current_url = urljoin(current_url, location)
                    
                    async with self._session.get(
                        current_url,
                        allow_redirects=False
                    ) as new_response:
                        current_response = new_response
                        
                # Check content type
                content_type = current_response.headers.get("Content-Type", "")
                base_content_type = content_type.split(";")[0].strip().lower()
                
                if base_content_type not in self.allowed_content_types:
                    return CrawlResult(
                        url=url,
                        status_code=current_response.status,
                        content_type=content_type,
                        error=f"Content type not allowed: {base_content_type}",
                        redirect_chain=redirect_chain,
                        crawl_time=time.time() - start_time
                    )
                    
                # Check content length
                content_length = current_response.headers.get("Content-Length")
                if content_length and int(content_length) > self.max_content_length:
                    return CrawlResult(
                        url=url,
                        status_code=current_response.status,
                        content_type=content_type,
                        content_length=int(content_length),
                        error=f"Content too large: {content_length} bytes",
                        redirect_chain=redirect_chain,
                        crawl_time=time.time() - start_time
                    )
                    
                # Read content with size limit
                content = ""
                content_bytes = 0
                
                async for chunk in current_response.content.iter_chunked(8192):
                    content_bytes += len(chunk)
                    if content_bytes > self.max_content_length:
                        raise Exception(f"Content exceeds {self.max_content_length} bytes")
                    content += chunk.decode("utf-8", errors="ignore")
                    
                # Parse content
                result = CrawlResult(
                    url=current_url,
                    status_code=current_response.status,
                    content=content,
                    content_type=content_type,
                    content_length=content_bytes,
                    headers=dict(current_response.headers),
                    redirect_chain=redirect_chain,
                    crawl_time=time.time() - start_time
                )
                
                # Extract links and metadata
                if base_content_type == "text/html":
                    self._extract_content(result, current_url)
                    
                return result
                
        except asyncio.TimeoutError:
            return CrawlResult(
                url=url,
                status_code=0,
                error="Request timeout",
                crawl_time=time.time() - start_time
            )
        except aiohttp.ClientError as e:
            return CrawlResult(
                url=url,
                status_code=0,
                error=f"Client error: {str(e)}",
                crawl_time=time.time() - start_time
            )
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=0,
                error=f"Unexpected error: {str(e)}",
                crawl_time=time.time() - start_time
            )
            
    def _extract_content(self, result: CrawlResult, base_url: str):
        """Extract links and metadata from HTML content"""
        try:
            soup = BeautifulSoup(result.content, "lxml")
            
            # Extract title
            title_tag = soup.find("title")
            if title_tag:
                result.title = title_tag.get_text(strip=True)
                
            # Extract meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                result.meta_description = meta_desc.get("content", "")
                
            # Extract links
            for link in soup.find_all(["a", "link"]):
                href = link.get("href")
                if href:
                    absolute_url = self._normalize_url(href, base_url)
                    if absolute_url:
                        result.links.append(absolute_url)
                        
            # Extract images
            for img in soup.find_all(["img", "source"]):
                src = img.get("src") or img.get("srcset")
                if src:
                    # Handle srcset
                    if "," in src:
                        src = src.split(",")[0].strip().split()[0]
                        
                    absolute_url = self._normalize_url(src, base_url)
                    if absolute_url:
                        result.images.append(absolute_url)
                        
            # Remove duplicates
            result.links = list(dict.fromkeys(result.links))
            result.images = list(dict.fromkeys(result.images))
            
        except Exception as e:
            logger.error(
                "Error extracting content",
                url=result.url,
                error=str(e)
            )
            
    def _normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """Normalize and validate URL"""
        try:
            # Remove fragment
            url, _ = urldefrag(url)
            
            # Skip certain schemes
            parsed = urlparse(url)
            if parsed.scheme in ("javascript", "mailto", "tel", "data"):
                return None
                
            # Make absolute
            absolute_url = urljoin(base_url, url)
            
            # Validate
            parsed = urlparse(absolute_url)
            if not parsed.scheme or not parsed.netloc:
                return None
                
            return absolute_url
            
        except Exception:
            return None
            
    async def crawl_batch(self, urls: List[str]) -> List[CrawlResult]:
        """Crawl multiple URLs concurrently"""
        tasks = [self.crawl(url) for url in urls]
        return await asyncio.gather(*tasks)
        
    def get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc.lower()
        
    def filter_same_domain_links(
        self,
        links: List[str],
        base_url: str
    ) -> List[str]:
        """Filter links to keep only same domain"""
        base_domain = self.get_domain(base_url)
        
        return [
            link for link in links
            if self.get_domain(link) == base_domain
        ]