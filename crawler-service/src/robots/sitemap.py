"""Sitemap parser for discovering URLs"""

import asyncio
import gzip
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, AsyncIterator
from datetime import datetime
from urllib.parse import urljoin, urlparse
from io import BytesIO

import aiohttp
from ultimate_sitemap_parser import SitemapParser as USP
import structlog

logger = structlog.get_logger(__name__)


class SitemapEntry:
    """Represents a single sitemap entry"""
    
    def __init__(
        self,
        loc: str,
        lastmod: Optional[datetime] = None,
        changefreq: Optional[str] = None,
        priority: Optional[float] = None
    ):
        self.loc = loc
        self.lastmod = lastmod
        self.changefreq = changefreq
        self.priority = priority
        
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "loc": self.loc,
            "lastmod": self.lastmod.isoformat() if self.lastmod else None,
            "changefreq": self.changefreq,
            "priority": self.priority
        }
        

class SitemapParser:
    """
    Parse XML sitemaps and sitemap index files.
    Supports compressed sitemaps and nested sitemap indexes.
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_size: int = 50_000_000,  # 50MB
        max_urls: int = 50_000,
        user_agent: str = "LLMOptimizer"
    ):
        self.timeout = timeout
        self.max_size = max_size
        self.max_urls = max_urls
        self.user_agent = user_agent
        
        # XML namespaces
        self.namespaces = {
            "": "http://www.sitemaps.org/schemas/sitemap/0.9",
            "image": "http://www.google.com/schemas/sitemap-image/1.1",
            "video": "http://www.google.com/schemas/sitemap-video/1.1",
            "news": "http://www.google.com/schemas/sitemap-news/0.9"
        }
        
    async def fetch_sitemap(self, url: str) -> Optional[bytes]:
        """Fetch sitemap content"""
        try:
            headers = {"User-Agent": self.user_agent}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    allow_redirects=True
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            "Failed to fetch sitemap",
                            url=url,
                            status=response.status
                        )
                        return None
                        
                    # Check content type
                    content_type = response.headers.get("Content-Type", "")
                    
                    # Read content with size limit
                    content = BytesIO()
                    total_size = 0
                    
                    async for chunk in response.content.iter_chunked(8192):
                        total_size += len(chunk)
                        if total_size > self.max_size:
                            logger.warning(
                                "Sitemap exceeds size limit",
                                url=url,
                                size=total_size
                            )
                            break
                        content.write(chunk)
                        
                    return content.getvalue()
                    
        except asyncio.TimeoutError:
            logger.error("Timeout fetching sitemap", url=url)
            return None
        except Exception as e:
            logger.error(
                "Error fetching sitemap",
                url=url,
                error=str(e)
            )
            return None
            
    async def parse_sitemap(
        self,
        url: str,
        content: Optional[bytes] = None,
        recurse: bool = True
    ) -> List[SitemapEntry]:
        """Parse sitemap and return entries"""
        if content is None:
            content = await self.fetch_sitemap(url)
            if not content:
                return []
                
        # Check if compressed
        if content.startswith(b'\x1f\x8b'):  # gzip magic number
            try:
                content = gzip.decompress(content)
            except Exception as e:
                logger.error(
                    "Failed to decompress sitemap",
                    url=url,
                    error=str(e)
                )
                return []
                
        # Parse XML
        try:
            entries = []
            
            # Check if sitemap index
            if b"<sitemapindex" in content:
                if recurse:
                    entries = await self._parse_sitemap_index(url, content)
            else:
                entries = self._parse_urlset(content)
                
            logger.info(
                "Parsed sitemap",
                url=url,
                entries_count=len(entries)
            )
            
            return entries[:self.max_urls]
            
        except ET.ParseError as e:
            logger.error(
                "Failed to parse sitemap XML",
                url=url,
                error=str(e)
            )
            return []
        except Exception as e:
            logger.error(
                "Error parsing sitemap",
                url=url,
                error=str(e)
            )
            return []
            
    async def _parse_sitemap_index(
        self,
        base_url: str,
        content: bytes
    ) -> List[SitemapEntry]:
        """Parse sitemap index file"""
        root = ET.fromstring(content)
        entries = []
        
        # Find all sitemap entries
        for sitemap in root.findall(".//sitemap", self.namespaces):
            loc_elem = sitemap.find("loc", self.namespaces)
            if loc_elem is not None and loc_elem.text:
                sitemap_url = urljoin(base_url, loc_elem.text.strip())
                
                # Parse nested sitemap
                nested_entries = await self.parse_sitemap(
                    sitemap_url,
                    recurse=False  # Avoid infinite recursion
                )
                entries.extend(nested_entries)
                
                if len(entries) >= self.max_urls:
                    break
                    
        return entries
        
    def _parse_urlset(self, content: bytes) -> List[SitemapEntry]:
        """Parse URL set from sitemap"""
        root = ET.fromstring(content)
        entries = []
        
        # Find all URL entries
        for url in root.findall(".//url", self.namespaces):
            loc_elem = url.find("loc", self.namespaces)
            if loc_elem is None or not loc_elem.text:
                continue
                
            entry = SitemapEntry(loc=loc_elem.text.strip())
            
            # Parse optional elements
            lastmod_elem = url.find("lastmod", self.namespaces)
            if lastmod_elem is not None and lastmod_elem.text:
                try:
                    entry.lastmod = datetime.fromisoformat(
                        lastmod_elem.text.strip().replace('Z', '+00:00')
                    )
                except ValueError:
                    pass
                    
            changefreq_elem = url.find("changefreq", self.namespaces)
            if changefreq_elem is not None and changefreq_elem.text:
                entry.changefreq = changefreq_elem.text.strip()
                
            priority_elem = url.find("priority", self.namespaces)
            if priority_elem is not None and priority_elem.text:
                try:
                    entry.priority = float(priority_elem.text.strip())
                except ValueError:
                    pass
                    
            entries.append(entry)
            
            if len(entries) >= self.max_urls:
                break
                
        return entries
        
    async def discover_sitemaps(self, domain: str) -> List[str]:
        """Discover sitemap URLs for a domain"""
        sitemap_urls = []
        base_url = f"https://{domain}"
        
        # Common sitemap locations
        common_paths = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemap-index.xml",
            "/sitemaps/sitemap.xml",
            "/sitemap/sitemap-index.xml",
            "/sitemap1.xml",
            "/sitemap.xml.gz",
            "/sitemap_index.xml.gz"
        ]
        
        # Check common locations
        for path in common_paths:
            url = urljoin(base_url, path)
            
            # Quick HEAD request to check existence
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(
                        url,
                        timeout=aiohttp.ClientTimeout(total=5.0),
                        allow_redirects=True
                    ) as response:
                        if response.status == 200:
                            sitemap_urls.append(url)
                            
            except Exception:
                pass
                
        # Also check robots.txt (handled by robots parser)
        
        return sitemap_urls
        
    async def parse_all_sitemaps(
        self,
        sitemap_urls: List[str]
    ) -> List[SitemapEntry]:
        """Parse multiple sitemaps concurrently"""
        tasks = [
            self.parse_sitemap(url)
            for url in sitemap_urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_entries = []
        for result in results:
            if isinstance(result, list):
                all_entries.extend(result)
                
        # Remove duplicates
        seen = set()
        unique_entries = []
        
        for entry in all_entries:
            if entry.loc not in seen:
                seen.add(entry.loc)
                unique_entries.append(entry)
                
        return unique_entries[:self.max_urls]
        
    def prioritize_entries(
        self,
        entries: List[SitemapEntry]
    ) -> List[SitemapEntry]:
        """Sort entries by priority and lastmod"""
        def sort_key(entry):
            # Higher priority first
            priority = entry.priority if entry.priority is not None else 0.5
            
            # Newer dates first
            if entry.lastmod:
                days_old = (datetime.now() - entry.lastmod).days
            else:
                days_old = 365  # Assume old if no date
                
            return (-priority, days_old)
            
        return sorted(entries, key=sort_key)