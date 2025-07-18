"""Tests for content type detection module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from content.detector import ContentDetector


class TestContentDetector:
    """Test cases for ContentDetector class."""
    
    @pytest.fixture
    def detector(self):
        """Create ContentDetector instance."""
        return ContentDetector()
    
    @pytest.mark.asyncio
    async def test_detect_png_by_magic_bytes(self, detector):
        """Test PNG detection by magic bytes."""
        # PNG magic bytes
        png_content = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A' + b'fake png data'
        
        result = await detector.detect_content_type(png_content)
        
        assert result['mime_type'] == 'image/png'
        assert result['description'] == 'PNG image'
        assert result['confidence'] >= 0.9
        assert result['details']['magic_bytes'] is True
    
    @pytest.mark.asyncio
    async def test_detect_jpeg_by_magic_bytes(self, detector):
        """Test JPEG detection by magic bytes."""
        jpeg_content = b'\xFF\xD8\xFF' + b'fake jpeg data'
        
        result = await detector.detect_content_type(jpeg_content)
        
        assert result['mime_type'] == 'image/jpeg'
        assert result['description'] == 'JPEG image'
        assert result['confidence'] >= 0.9
    
    @pytest.mark.asyncio
    async def test_detect_pdf_by_magic_bytes(self, detector):
        """Test PDF detection by magic bytes."""
        pdf_content = b'\x25\x50\x44\x46' + b'-1.4 fake pdf data'
        
        result = await detector.detect_content_type(pdf_content)
        
        assert result['mime_type'] == 'application/pdf'
        assert result['description'] == 'PDF document'
        assert result['confidence'] >= 0.9
    
    @pytest.mark.asyncio
    async def test_detect_webp_format(self, detector):
        """Test WebP format detection."""
        webp_content = b'RIFF\x00\x00\x00\x00WEBP' + b'fake webp data'
        
        result = await detector.detect_content_type(webp_content)
        
        assert result['mime_type'] == 'image/webp'
        assert result['description'] == 'WebP image'
    
    @pytest.mark.asyncio
    async def test_detect_by_url_extension(self, detector):
        """Test content type detection by URL extension."""
        text_content = b'This is plain text content'
        url = 'https://example.com/document.txt'
        
        result = await detector.detect_content_type(text_content, url=url)
        
        assert result['mime_type'] == 'text/plain'
        assert result['details'].get('url_extension') == '.txt'
    
    @pytest.mark.asyncio
    async def test_detect_encoding_utf8(self, detector):
        """Test UTF-8 encoding detection."""
        utf8_content = 'Hello, 世界! Привет!'.encode('utf-8')
        
        result = await detector.detect_content_type(utf8_content)
        
        assert result['encoding'] == 'utf-8'
        assert result['details']['encoding_confidence'] > 0.7
    
    @pytest.mark.asyncio
    async def test_detect_encoding_iso_8859_1(self, detector):
        """Test ISO-8859-1 encoding detection."""
        iso_content = 'Café naïve résumé'.encode('iso-8859-1')
        
        encoding_result = await detector._detect_encoding(iso_content)
        
        assert encoding_result['encoding'] in ['iso-8859-1', 'windows-1252']
        assert encoding_result['confidence'] > 0.5
    
    @pytest.mark.asyncio
    async def test_detect_html_structure(self, detector):
        """Test HTML structure detection."""
        html_content = b'''<!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body><h1>Hello World</h1></body>
        </html>'''
        
        result = await detector.detect_content_type(html_content)
        
        assert result['mime_type'] == 'text/html'
        assert result['structure'] == 'html'
    
    @pytest.mark.asyncio
    async def test_detect_json_structure(self, detector):
        """Test JSON structure detection."""
        json_content = b'{"name": "test", "value": 123, "array": [1, 2, 3]}'
        
        result = await detector.detect_content_type(json_content)
        
        assert result['structure'] == 'json'
    
    @pytest.mark.asyncio
    async def test_detect_xml_structure(self, detector):
        """Test XML structure detection."""
        xml_content = b'<?xml version="1.0"?><root><item>test</item></root>'
        
        result = await detector.detect_content_type(xml_content)
        
        assert result['structure'] == 'xml'
    
    @pytest.mark.asyncio
    @patch('langdetect.detect')
    async def test_detect_language(self, mock_detect, detector):
        """Test language detection."""
        mock_detect.return_value = 'en'
        
        english_content = b'This is a test document in English language.'
        
        result = await detector.detect_content_type(english_content)
        
        assert result['language'] == 'en'
        mock_detect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detect_with_http_headers(self, detector):
        """Test content type detection with HTTP headers."""
        content = b'Some content'
        headers = {
            'content-type': 'application/json; charset=utf-8'
        }
        
        result = await detector.detect_content_type(content, headers=headers)
        
        assert result['mime_type'] == 'application/json'
        assert result['encoding'] == 'utf-8'
        assert result['details']['http_header'] == 'application/json; charset=utf-8'
    
    def test_calculate_confidence_multiple_confirmations(self, detector):
        """Test confidence calculation with multiple confirmations."""
        results = {
            'confidence': 0.8,
            'details': {
                'magic_bytes': True,
                'libmagic': {'mime': 'image/png'},
                'http_header': 'image/png',
                'url_extension': '.png'
            },
            'mime_type': 'image/png'
        }
        
        confidence = detector._calculate_confidence(results)
        
        assert confidence > 0.8  # Should be boosted by multiple confirmations
        assert confidence <= 1.0
    
    def test_calculate_confidence_generic_type(self, detector):
        """Test confidence reduction for generic types."""
        results = {
            'confidence': 0.9,
            'details': {},
            'mime_type': 'application/octet-stream'
        }
        
        confidence = detector._calculate_confidence(results)
        
        assert confidence < 0.9  # Should be reduced for generic type
    
    def test_get_content_hash(self, detector):
        """Test content hash generation."""
        content = b'Test content for hashing'
        
        hashes = detector.get_content_hash(content)
        
        assert 'md5' in hashes
        assert 'sha1' in hashes
        assert 'sha256' in hashes
        assert 'size' in hashes
        assert hashes['size'] == len(content)
        assert len(hashes['sha256']) == 64  # SHA-256 hex string length
    
    @pytest.mark.asyncio
    async def test_detect_short_content(self, detector):
        """Test detection with very short content."""
        short_content = b'Hi'
        
        result = await detector.detect_content_type(short_content)
        
        assert result['mime_type'] is not None
        assert result['confidence'] <= 0.8  # Lower confidence for short content
    
    @pytest.mark.asyncio
    async def test_detect_markdown_structure(self, detector):
        """Test Markdown structure detection."""
        markdown_content = b'''# Header 1
        ## Header 2
        
        - List item 1
        - List item 2
        
        ***
        
        Some **bold** text and *italic* text.
        '''
        
        result = await detector.detect_content_type(markdown_content)
        
        assert result['structure'] == 'markdown'
    
    @pytest.mark.asyncio
    async def test_detect_python_code(self, detector):
        """Test Python code detection."""
        python_content = b'''import os
        
        def main():
            print("Hello World")
        
        if __name__ == "__main__":
            main()
        '''
        
        result = await detector.detect_content_type(python_content)
        
        assert result['structure'] == 'python'
    
    @pytest.mark.asyncio
    async def test_detect_css_code(self, detector):
        """Test CSS code detection."""
        css_content = b'''.container {
            width: 100%;
            margin: 0 auto;
        }
        
        @media (max-width: 768px) {
            .container { width: 90%; }
        }
        '''
        
        result = await detector.detect_content_type(css_content)
        
        assert result['structure'] == 'css'
    
    @pytest.mark.asyncio
    @patch('magic.Magic.from_buffer')
    async def test_libmagic_failure_handling(self, mock_magic, detector):
        """Test handling of libmagic failures."""
        mock_magic.side_effect = Exception("Magic library error")
        
        content = b'Some content'
        
        result = await detector.detect_content_type(content)
        
        # Should still return a result even if libmagic fails
        assert 'mime_type' in result
        assert 'confidence' in result