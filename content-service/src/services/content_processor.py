import re
import html
from typing import Dict, Any, Optional
import logging
from bs4 import BeautifulSoup
import langdetect
from langdetect import detect_langs
import bleach

logger = logging.getLogger(__name__)

class ContentProcessor:
    """Service for processing and validating content"""
    
    # Allowed HTML tags for sanitization
    ALLOWED_TAGS = [
        'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'em', 'u', 'i', 'b', 'a', 'ul', 'ol', 'li',
        'blockquote', 'code', 'pre', 'img', 'table', 'thead', 'tbody',
        'tr', 'th', 'td'
    ]
    
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'blockquote': ['cite'],
        'code': ['class']
    }
    
    def __init__(self):
        self.min_content_length = 10
        self.max_content_length = 100000
    
    async def process_content(
        self,
        content: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process and validate content"""
        try:
            # Basic validation
            if not content or len(content.strip()) < self.min_content_length:
                raise ValueError("Content is too short")
            
            if len(content) > self.max_content_length:
                raise ValueError("Content exceeds maximum length")
            
            # Detect content format
            content_format = self._detect_content_format(content)
            
            # Sanitize content
            sanitized_content = self._sanitize_content(content, content_format)
            
            # Extract text for analysis
            plain_text = self._extract_plain_text(sanitized_content, content_format)
            
            # Detect language
            language = self._detect_language(plain_text)
            
            # Calculate content statistics
            stats = self._calculate_stats(plain_text)
            
            # Extract metadata
            extracted_metadata = self._extract_metadata(sanitized_content, content_format)
            
            # Classify content type if not provided
            if content_type == "auto":
                content_type = self._classify_content_type(plain_text, stats)
            
            return {
                "success": True,
                "sanitized_content": sanitized_content,
                "plain_text": plain_text,
                "content_format": content_format,
                "language": language,
                "stats": stats,
                "metadata": {
                    **(metadata or {}),
                    **extracted_metadata,
                    "content_type_detected": content_type
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _detect_content_format(self, content: str) -> str:
        """Detect if content is HTML, Markdown, or plain text"""
        # Check for HTML tags
        if bool(BeautifulSoup(content, "html.parser").find()):
            return "html"
        
        # Check for Markdown patterns
        markdown_patterns = [
            r'^#{1,6}\s',  # Headers
            r'\*\*.*\*\*',  # Bold
            r'\[.*\]\(.*\)',  # Links
            r'^[-*+]\s',  # Lists
            r'```',  # Code blocks
        ]
        
        for pattern in markdown_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return "markdown"
        
        return "plain"
    
    def _sanitize_content(self, content: str, content_format: str) -> str:
        """Sanitize content based on format"""
        if content_format == "html":
            # Use bleach to sanitize HTML
            return bleach.clean(
                content,
                tags=self.ALLOWED_TAGS,
                attributes=self.ALLOWED_ATTRIBUTES,
                strip=True
            )
        elif content_format == "markdown":
            # Basic markdown sanitization
            # Remove potential script injections
            content = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
            return content
        else:
            # Plain text - just escape HTML
            return html.escape(content)
    
    def _extract_plain_text(self, content: str, content_format: str) -> str:
        """Extract plain text from content"""
        if content_format == "html":
            soup = BeautifulSoup(content, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator=' ', strip=True)
        elif content_format == "markdown":
            # Simple markdown to text conversion
            # Remove markdown syntax
            text = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)  # Headers
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
            text = re.sub(r'\*(.*?)\*', r'\1', text)  # Italic
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links
            text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)  # Code blocks
            text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
            return text.strip()
        else:
            return content.strip()
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of the text"""
        try:
            # Use langdetect to detect language
            detections = detect_langs(text[:1000])  # Use first 1000 chars for speed
            if detections:
                return detections[0].lang
            return "unknown"
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return "unknown"
    
    def _calculate_stats(self, text: str) -> Dict[str, Any]:
        """Calculate content statistics"""
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return {
            "character_count": len(text),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "average_word_length": sum(len(word) for word in words) / len(words) if words else 0,
            "average_sentence_length": len(words) / len(sentences) if sentences else 0,
            "paragraph_count": len(re.split(r'\n\n+', text.strip()))
        }
    
    def _extract_metadata(self, content: str, content_format: str) -> Dict[str, Any]:
        """Extract metadata from content"""
        metadata = {}
        
        if content_format == "html":
            soup = BeautifulSoup(content, "html.parser")
            
            # Extract title from h1 or first heading
            heading = soup.find(['h1', 'h2', 'h3'])
            if heading:
                metadata["extracted_title"] = heading.get_text(strip=True)
            
            # Extract images
            images = soup.find_all('img')
            if images:
                metadata["image_count"] = len(images)
                metadata["images"] = [
                    {
                        "src": img.get('src', ''),
                        "alt": img.get('alt', '')
                    }
                    for img in images[:5]  # Limit to first 5
                ]
            
            # Extract links
            links = soup.find_all('a', href=True)
            if links:
                metadata["link_count"] = len(links)
                metadata["links"] = [
                    {
                        "href": link.get('href', ''),
                        "text": link.get_text(strip=True)
                    }
                    for link in links[:5]  # Limit to first 5
                ]
        
        return metadata
    
    def _classify_content_type(self, text: str, stats: Dict[str, Any]) -> str:
        """Attempt to classify content type based on text analysis"""
        word_count = stats.get("word_count", 0)
        avg_sentence_length = stats.get("average_sentence_length", 0)
        
        # Simple heuristics for content type classification
        if word_count < 50:
            return "social_media"
        elif word_count < 200:
            if avg_sentence_length < 15:
                return "product_description"
            else:
                return "email"
        elif word_count < 500:
            return "blog_post"
        else:
            return "article"