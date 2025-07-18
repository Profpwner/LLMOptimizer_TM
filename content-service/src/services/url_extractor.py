import aiohttp
import asyncio
from typing import Dict, Any, Optional
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import chardet

logger = logging.getLogger(__name__)

class URLExtractor:
    """Service for extracting content from URLs"""
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.max_content_size = 10 * 1024 * 1024  # 10MB
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Compatible) LLMOptimizer/1.0'
        }
    
    async def extract_from_url(self, url: str) -> Dict[str, Any]:
        """Extract content from a URL"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self.headers) as response:
                    # Check response status
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {response.reason}"
                        }
                    
                    # Check content type
                    content_type = response.headers.get('Content-Type', '').lower()
                    if not any(ct in content_type for ct in ['text/html', 'text/plain', 'application/xhtml']):
                        return {
                            "success": False,
                            "error": f"Unsupported content type: {content_type}"
                        }
                    
                    # Check content size
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > self.max_content_size:
                        return {
                            "success": False,
                            "error": "Content size exceeds maximum limit"
                        }
                    
                    # Read content
                    content_bytes = await response.read()
                    
                    # Detect encoding
                    encoding = self._detect_encoding(content_bytes, response.headers)
                    content = content_bytes.decode(encoding, errors='ignore')
                    
                    # Parse and extract content
                    if 'html' in content_type:
                        extracted = self._extract_from_html(content, url)
                    else:
                        extracted = self._extract_from_text(content)
                    
                    return {
                        "success": True,
                        "content": extracted["content"],
                        "title": extracted.get("title", ""),
                        "metadata": {
                            "url": url,
                            "content_type": content_type,
                            "encoding": encoding,
                            **extracted.get("metadata", {})
                        }
                    }
                    
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timeout"
            }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"Client error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error extracting from URL {url}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _detect_encoding(self, content_bytes: bytes, headers: dict) -> str:
        """Detect content encoding"""
        # Try to get from headers first
        content_type = headers.get('Content-Type', '')
        if 'charset=' in content_type:
            return content_type.split('charset=')[-1].strip('"\'')
        
        # Use chardet to detect
        detection = chardet.detect(content_bytes)
        if detection['confidence'] > 0.7:
            return detection['encoding']
        
        # Default to UTF-8
        return 'utf-8'
    
    def _extract_from_html(self, html_content: str, base_url: str) -> Dict[str, Any]:
        """Extract content from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        
        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)
        
        # Extract meta description
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '')
        
        # Extract author
        author = ""
        author_meta = soup.find('meta', attrs={'name': 'author'})
        if author_meta:
            author = author_meta.get('content', '')
        
        # Extract main content
        content = self._extract_main_content(soup)
        
        # Extract images
        images = []
        for img in soup.find_all('img', src=True)[:10]:  # Limit to 10 images
            img_url = urljoin(base_url, img['src'])
            images.append({
                'src': img_url,
                'alt': img.get('alt', ''),
                'title': img.get('title', '')
            })
        
        # Extract OpenGraph data
        og_data = {}
        for meta in soup.find_all('meta', property=True):
            if meta['property'].startswith('og:'):
                og_data[meta['property']] = meta.get('content', '')
        
        return {
            "content": content,
            "title": title,
            "metadata": {
                "description": description,
                "author": author,
                "images": images,
                "opengraph": og_data
            }
        }
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML"""
        # Try to find main content areas
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.content',
            '#content',
            '.post',
            '.entry-content',
            '.article-content',
            '.post-content'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(separator='\n', strip=True)
        
        # Fallback to body content
        body = soup.find('body')
        if body:
            # Remove navigation, footer, etc.
            for element in body(['nav', 'header', 'footer', 'aside']):
                element.decompose()
            return body.get_text(separator='\n', strip=True)
        
        # Last resort - get all text
        return soup.get_text(separator='\n', strip=True)
    
    def _extract_from_text(self, text_content: str) -> Dict[str, Any]:
        """Extract content from plain text"""
        lines = text_content.strip().split('\n')
        
        # Try to extract title from first non-empty line
        title = ""
        for line in lines:
            if line.strip():
                title = line.strip()[:200]  # Limit title length
                break
        
        return {
            "content": text_content,
            "title": title,
            "metadata": {
                "format": "plain_text"
            }
        }