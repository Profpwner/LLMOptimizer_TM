"""
Response compression middleware for API optimization.
"""

import gzip
import brotli
import zstandard as zstd
from typing import Dict, List, Optional, Union, Callable
from dataclasses import dataclass
import asyncio
import json
import msgpack
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers, MutableHeaders
import logging

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """Configuration for compression middleware."""
    enable_gzip: bool = True
    enable_brotli: bool = True
    enable_zstd: bool = True
    min_size: int = 1024  # Minimum size in bytes to compress
    gzip_level: int = 6  # 1-9, higher = better compression
    brotli_quality: int = 4  # 0-11, higher = better compression
    zstd_level: int = 3  # 1-22, higher = better compression
    excluded_paths: List[str] = None
    excluded_content_types: List[str] = None


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    High-performance compression middleware for FastAPI.
    Supports gzip, brotli, and zstandard compression.
    """
    
    def __init__(self, app, config: Optional[CompressionConfig] = None):
        super().__init__(app)
        self.config = config or CompressionConfig()
        
        # Initialize compressors
        self.compressors = self._init_compressors()
        
        # Default excluded content types
        if self.config.excluded_content_types is None:
            self.config.excluded_content_types = [
                'image/', 'video/', 'audio/', 'application/zip',
                'application/gzip', 'application/x-bzip2'
            ]
    
    def _init_compressors(self) -> Dict[str, Callable]:
        """Initialize compression algorithms."""
        compressors = {}
        
        if self.config.enable_gzip:
            compressors['gzip'] = lambda data: gzip.compress(
                data, compresslevel=self.config.gzip_level
            )
        
        if self.config.enable_brotli:
            compressors['br'] = lambda data: brotli.compress(
                data, quality=self.config.brotli_quality
            )
        
        if self.config.enable_zstd:
            zstd_cctx = zstd.ZstdCompressor(level=self.config.zstd_level)
            compressors['zstd'] = zstd_cctx.compress
        
        return compressors
    
    async def dispatch(self, request: Request, call_next):
        """Process request and compress response if applicable."""
        # Check if path is excluded
        if self._is_path_excluded(request.url.path):
            return await call_next(request)
        
        # Get accepted encodings
        accept_encoding = request.headers.get('accept-encoding', '')
        selected_encoding = self._select_encoding(accept_encoding)
        
        # Process request
        response = await call_next(request)
        
        # Check if we should compress
        if not self._should_compress(response, selected_encoding):
            return response
        
        # Compress response
        return await self._compress_response(response, selected_encoding)
    
    def _is_path_excluded(self, path: str) -> bool:
        """Check if path is excluded from compression."""
        if not self.config.excluded_paths:
            return False
        
        return any(path.startswith(excluded) for excluded in self.config.excluded_paths)
    
    def _select_encoding(self, accept_encoding: str) -> Optional[str]:
        """Select best encoding based on client preferences."""
        if not accept_encoding:
            return None
        
        # Parse accept-encoding header
        encodings = self._parse_accept_encoding(accept_encoding)
        
        # Select best available encoding
        for encoding, _ in encodings:
            if encoding in self.compressors:
                return encoding
        
        return None
    
    def _parse_accept_encoding(self, accept_encoding: str) -> List[tuple]:
        """Parse Accept-Encoding header and return sorted by quality."""
        encodings = []
        
        for part in accept_encoding.split(','):
            part = part.strip()
            if ';' in part:
                encoding, q_value = part.split(';', 1)
                try:
                    q = float(q_value.split('=')[1])
                except (IndexError, ValueError):
                    q = 1.0
            else:
                encoding = part
                q = 1.0
            
            encodings.append((encoding.strip(), q))
        
        # Sort by quality (highest first)
        return sorted(encodings, key=lambda x: x[1], reverse=True)
    
    def _should_compress(self, response: Response, encoding: Optional[str]) -> bool:
        """Determine if response should be compressed."""
        if not encoding:
            return False
        
        # Check if already compressed
        if response.headers.get('content-encoding'):
            return False
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if any(excluded in content_type for excluded in self.config.excluded_content_types):
            return False
        
        # Check content length
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) < self.config.min_size:
            return False
        
        return True
    
    async def _compress_response(self, response: Response, encoding: str) -> Response:
        """Compress response body."""
        # Read response body
        body = b''
        async for chunk in response.body_iterator:
            body += chunk
        
        # Check size after reading
        if len(body) < self.config.min_size:
            # Return uncompressed
            response.body = body
            return response
        
        # Compress body
        compressed_body = await asyncio.get_event_loop().run_in_executor(
            None, self.compressors[encoding], body
        )
        
        # Update response
        response.body = compressed_body
        response.headers['content-encoding'] = encoding
        response.headers['content-length'] = str(len(compressed_body))
        
        # Add Vary header
        vary = response.headers.get('vary', '')
        if vary:
            response.headers['vary'] = f"{vary}, Accept-Encoding"
        else:
            response.headers['vary'] = "Accept-Encoding"
        
        logger.debug(
            f"Compressed response: {len(body)} -> {len(compressed_body)} bytes "
            f"({100 * (1 - len(compressed_body) / len(body)):.1f}% reduction)"
        )
        
        return response


class MessagePackMiddleware(BaseHTTPMiddleware):
    """
    Middleware for MessagePack serialization for better performance.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request with MessagePack support."""
        # Check if client accepts msgpack
        accept = request.headers.get('accept', '')
        
        # Process request
        response = await call_next(request)
        
        # Check if we should convert to msgpack
        if 'application/msgpack' in accept and response.headers.get('content-type') == 'application/json':
            # Convert JSON to MessagePack
            body = b''
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                # Parse JSON and convert to MessagePack
                data = json.loads(body)
                msgpack_body = msgpack.packb(data, use_bin_type=True)
                
                # Update response
                response.body = msgpack_body
                response.headers['content-type'] = 'application/msgpack'
                response.headers['content-length'] = str(len(msgpack_body))
                
                logger.debug(f"Converted JSON to MessagePack: {len(body)} -> {len(msgpack_body)} bytes")
            except Exception as e:
                logger.error(f"Failed to convert to MessagePack: {e}")
        
        return response


def create_compression_middleware(
    app,
    min_size: int = 1024,
    enable_msgpack: bool = True
) -> List[BaseHTTPMiddleware]:
    """Create compression middleware stack."""
    middlewares = []
    
    # Add compression middleware
    config = CompressionConfig(min_size=min_size)
    middlewares.append(CompressionMiddleware(app, config))
    
    # Add MessagePack middleware
    if enable_msgpack:
        middlewares.append(MessagePackMiddleware(app))
    
    return middlewares


class StreamingCompressor:
    """
    Compressor for streaming responses (e.g., SSE, WebSocket).
    """
    
    def __init__(self, encoding: str = 'gzip', level: int = 6):
        self.encoding = encoding
        
        if encoding == 'gzip':
            self.compressor = gzip.GzipFile(mode='wb', compresslevel=level)
        elif encoding == 'br':
            self.compressor = brotli.Compressor(quality=level)
        elif encoding == 'zstd':
            self.compressor = zstd.ZstdCompressor(level=level).compressobj()
        else:
            raise ValueError(f"Unsupported encoding: {encoding}")
    
    def compress_chunk(self, data: bytes) -> bytes:
        """Compress a single chunk of data."""
        if self.encoding == 'gzip':
            self.compressor.write(data)
            return self.compressor.read()
        elif self.encoding == 'br':
            return self.compressor.process(data)
        elif self.encoding == 'zstd':
            return self.compressor.compress(data)
    
    def flush(self) -> bytes:
        """Flush any remaining compressed data."""
        if self.encoding == 'gzip':
            self.compressor.close()
            return self.compressor.read()
        elif self.encoding == 'br':
            return self.compressor.finish()
        elif self.encoding == 'zstd':
            return self.compressor.flush()


# Compression utilities for specific content types
class JSONCompressor:
    """Optimized JSON compression."""
    
    @staticmethod
    def compress_json(data: Union[dict, list], encoding: str = 'gzip') -> bytes:
        """Compress JSON data efficiently."""
        # Use compact JSON representation
        json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
        
        if encoding == 'gzip':
            return gzip.compress(json_bytes, compresslevel=6)
        elif encoding == 'br':
            return brotli.compress(json_bytes, quality=4)
        elif encoding == 'zstd':
            return zstd.compress(json_bytes, 3)
        else:
            return json_bytes
    
    @staticmethod
    def decompress_json(data: bytes, encoding: str = 'gzip') -> Union[dict, list]:
        """Decompress JSON data."""
        if encoding == 'gzip':
            json_bytes = gzip.decompress(data)
        elif encoding == 'br':
            json_bytes = brotli.decompress(data)
        elif encoding == 'zstd':
            json_bytes = zstd.decompress(data)
        else:
            json_bytes = data
        
        return json.loads(json_bytes.decode('utf-8'))


# Compression benchmarking
async def benchmark_compression(data: bytes) -> Dict[str, Dict[str, float]]:
    """Benchmark different compression algorithms."""
    import time
    
    results = {}
    
    # Test each algorithm
    algorithms = {
        'gzip': lambda d: gzip.compress(d, compresslevel=6),
        'brotli': lambda d: brotli.compress(d, quality=4),
        'zstd': lambda d: zstd.compress(d, 3)
    }
    
    for name, compress_func in algorithms.items():
        start_time = time.time()
        compressed = compress_func(data)
        compression_time = time.time() - start_time
        
        results[name] = {
            'compression_time': compression_time,
            'compressed_size': len(compressed),
            'compression_ratio': len(compressed) / len(data),
            'throughput_mbps': (len(data) / compression_time) / (1024 * 1024)
        }
    
    return results