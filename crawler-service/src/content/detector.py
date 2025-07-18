"""Advanced content type detection with magic bytes, MIME analysis, and encoding detection."""

import magic
import chardet
from langdetect import detect, LangDetectException
import mimetypes
import hashlib
from typing import Dict, Optional, Tuple, Any
from pathlib import Path
import struct
import re
from urllib.parse import urlparse
import ftfy

import structlog

logger = structlog.get_logger(__name__)


class ContentDetector:
    """Advanced content type detection with confidence scoring."""
    
    # Magic byte signatures for common file types
    MAGIC_BYTES = {
        b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': ('image/png', 'PNG image'),
        b'\xFF\xD8\xFF': ('image/jpeg', 'JPEG image'),
        b'\x47\x49\x46\x38\x37\x61': ('image/gif', 'GIF87a image'),
        b'\x47\x49\x46\x38\x39\x61': ('image/gif', 'GIF89a image'),
        b'\x25\x50\x44\x46': ('application/pdf', 'PDF document'),
        b'\x50\x4B\x03\x04': ('application/zip', 'ZIP archive'),
        b'\x1F\x8B\x08': ('application/gzip', 'GZIP archive'),
        b'\x42\x5A\x68': ('application/x-bzip2', 'BZIP2 archive'),
        b'\x52\x49\x46\x46': ('image/webp', 'WebP image'),
        b'\x00\x00\x00\x0C\x6A\x50\x20\x20': ('image/jp2', 'JPEG 2000'),
        b'\x00\x00\x00\x18\x66\x74\x79\x70': ('video/mp4', 'MP4 video'),
        b'\x1A\x45\xDF\xA3': ('video/webm', 'WebM video'),
        b'\x00\x00\x01\xBA': ('video/mpeg', 'MPEG video'),
        b'\x00\x00\x01\xB3': ('video/mpeg', 'MPEG video'),
        b'\x52\x49\x46\x46': ('audio/wav', 'WAV audio'),
        b'\x49\x44\x33': ('audio/mp3', 'MP3 audio'),
        b'\x66\x4C\x61\x43': ('audio/flac', 'FLAC audio'),
        b'\x4F\x67\x67\x53': ('audio/ogg', 'OGG audio'),
    }
    
    # Common text encodings
    TEXT_ENCODINGS = [
        'utf-8', 'utf-16', 'utf-32', 'ascii', 'iso-8859-1', 'iso-8859-2',
        'windows-1252', 'windows-1251', 'gb2312', 'gbk', 'big5', 'shift_jis',
        'euc-jp', 'euc-kr'
    ]
    
    # Content structure patterns
    STRUCTURE_PATTERNS = {
        'html': re.compile(r'<html[^>]*>|<!DOCTYPE\s+html', re.IGNORECASE),
        'xml': re.compile(r'<\?xml[^>]+\?>|<[^>]+xmlns[^>]*>', re.IGNORECASE),
        'json': re.compile(r'^\s*[\{\[]'),
        'yaml': re.compile(r'^---\s*$|^[a-zA-Z_]+:\s*', re.MULTILINE),
        'csv': re.compile(r'^[^,\n]+,[^,\n]+', re.MULTILINE),
        'markdown': re.compile(r'^#{1,6}\s+|^\*{3,}|^-{3,}', re.MULTILINE),
        'javascript': re.compile(r'function\s+\w+|var\s+\w+|const\s+\w+|let\s+\w+'),
        'css': re.compile(r'[.#]\w+\s*\{|@media|@import'),
        'python': re.compile(r'def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+\s+import'),
    }
    
    def __init__(self):
        """Initialize content detector with magic library."""
        self.mime_detector = magic.Magic(mime=True)
        self.file_detector = magic.Magic(mime=False)
        mimetypes.init()
    
    async def detect_content_type(
        self, 
        content: bytes, 
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive content type detection.
        
        Args:
            content: Raw content bytes
            url: Optional URL for extension-based detection
            headers: Optional HTTP headers
            
        Returns:
            Detection results with confidence scores
        """
        results = {
            'mime_type': None,
            'encoding': None,
            'language': None,
            'structure': None,
            'description': None,
            'confidence': 0.0,
            'details': {}
        }
        
        # 1. Magic byte detection
        magic_result = self._detect_by_magic_bytes(content)
        if magic_result:
            results['mime_type'] = magic_result[0]
            results['description'] = magic_result[1]
            results['confidence'] = 0.9
            results['details']['magic_bytes'] = True
        
        # 2. libmagic detection
        try:
            mime_type = self.mime_detector.from_buffer(content)
            file_type = self.file_detector.from_buffer(content)
            
            if not results['mime_type'] or mime_type != 'application/octet-stream':
                results['mime_type'] = mime_type
                results['description'] = file_type
                if results['confidence'] < 0.8:
                    results['confidence'] = 0.8
                results['details']['libmagic'] = {
                    'mime': mime_type,
                    'description': file_type
                }
        except Exception as e:
            logger.warning(f"libmagic detection failed: {e}")
        
        # 3. Header-based detection
        if headers:
            content_type = headers.get('content-type', '').lower()
            if content_type:
                mime_type = content_type.split(';')[0].strip()
                if not results['mime_type'] or results['confidence'] < 0.7:
                    results['mime_type'] = mime_type
                    results['confidence'] = max(results['confidence'], 0.7)
                results['details']['http_header'] = content_type
                
                # Extract charset from Content-Type
                charset_match = re.search(r'charset=([^;]+)', content_type)
                if charset_match:
                    results['encoding'] = charset_match.group(1).strip()
        
        # 4. URL extension-based detection
        if url:
            parsed_url = urlparse(url)
            path = parsed_url.path
            if path:
                mime_type, _ = mimetypes.guess_type(path)
                if mime_type and (not results['mime_type'] or results['confidence'] < 0.6):
                    results['mime_type'] = mime_type
                    results['confidence'] = max(results['confidence'], 0.6)
                    results['details']['url_extension'] = Path(path).suffix
        
        # 5. Encoding detection for text content
        if results['mime_type'] and results['mime_type'].startswith('text/'):
            encoding_result = await self._detect_encoding(content)
            results['encoding'] = encoding_result['encoding']
            results['details']['encoding_confidence'] = encoding_result['confidence']
            
            # Decode and detect language
            try:
                text = content.decode(results['encoding'])
                text = ftfy.fix_text(text)  # Fix mojibake
                
                # Structure detection
                structure = self._detect_structure(text)
                if structure:
                    results['structure'] = structure
                    results['details']['structure_detected'] = structure
                
                # Language detection
                language = await self._detect_language(text)
                if language:
                    results['language'] = language
            except Exception as e:
                logger.warning(f"Text processing failed: {e}")
        
        # 6. Calculate final confidence
        results['confidence'] = self._calculate_confidence(results)
        
        return results
    
    def _detect_by_magic_bytes(self, content: bytes) -> Optional[Tuple[str, str]]:
        """Detect content type by magic byte signatures."""
        if len(content) < 8:
            return None
            
        for signature, (mime_type, description) in self.MAGIC_BYTES.items():
            if content.startswith(signature):
                return (mime_type, description)
        
        # Check RIFF-based formats (WebP, WAV)
        if content.startswith(b'RIFF') and len(content) >= 12:
            format_type = content[8:12]
            if format_type == b'WEBP':
                return ('image/webp', 'WebP image')
            elif format_type == b'WAVE':
                return ('audio/wav', 'WAV audio')
        
        return None
    
    async def _detect_encoding(self, content: bytes) -> Dict[str, Any]:
        """Detect character encoding with confidence score."""
        # Try chardet first
        try:
            detection = chardet.detect(content)
            if detection['confidence'] > 0.7:
                return {
                    'encoding': detection['encoding'],
                    'confidence': detection['confidence']
                }
        except Exception as e:
            logger.warning(f"chardet detection failed: {e}")
        
        # Try common encodings
        for encoding in self.TEXT_ENCODINGS:
            try:
                content.decode(encoding)
                return {
                    'encoding': encoding,
                    'confidence': 0.5
                }
            except (UnicodeDecodeError, LookupError):
                continue
        
        return {
            'encoding': 'utf-8',
            'confidence': 0.1
        }
    
    def _detect_structure(self, text: str) -> Optional[str]:
        """Detect content structure (HTML, XML, JSON, etc.)."""
        # Limit text for performance
        sample = text[:10000]
        
        for structure, pattern in self.STRUCTURE_PATTERNS.items():
            if pattern.search(sample):
                return structure
        
        return None
    
    async def _detect_language(self, text: str) -> Optional[str]:
        """Detect natural language of text content."""
        try:
            # Clean and limit text for detection
            clean_text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
            clean_text = re.sub(r'\s+', ' ', clean_text)  # Normalize whitespace
            clean_text = clean_text[:1000]  # Limit length
            
            if len(clean_text.strip()) > 20:
                return detect(clean_text)
        except LangDetectException:
            pass
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
        
        return None
    
    def _calculate_confidence(self, results: Dict[str, Any]) -> float:
        """Calculate overall confidence score based on detection results."""
        confidence = results.get('confidence', 0.0)
        
        # Boost confidence based on multiple confirmations
        confirmations = 0
        
        if results['details'].get('magic_bytes'):
            confirmations += 1
        if results['details'].get('libmagic'):
            confirmations += 1
        if results['details'].get('http_header'):
            confirmations += 1
        if results['details'].get('url_extension'):
            confirmations += 1
        
        if confirmations > 1:
            confidence = min(1.0, confidence + (confirmations - 1) * 0.1)
        
        # Reduce confidence for generic types
        if results['mime_type'] in ['application/octet-stream', 'text/plain']:
            confidence *= 0.8
        
        return round(confidence, 2)
    
    def get_content_hash(self, content: bytes) -> Dict[str, str]:
        """Calculate various hashes for content identification."""
        return {
            'md5': hashlib.md5(content).hexdigest(),
            'sha1': hashlib.sha1(content).hexdigest(),
            'sha256': hashlib.sha256(content).hexdigest(),
            'size': len(content)
        }