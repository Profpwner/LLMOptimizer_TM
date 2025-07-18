"""
Performance optimization module for handling 100K+ concurrent users.

This module provides:
- Database connection pooling
- Query optimization
- Async processing
- Response compression
- Request batching
- Memory optimization
"""

from .connection_pool import ConnectionPoolManager
from .query_optimizer import QueryOptimizer
from .async_processor import AsyncProcessor
from .compression import CompressionMiddleware
from .batch_processor import BatchProcessor
from .memory_optimizer import MemoryOptimizer

__all__ = [
    'ConnectionPoolManager',
    'QueryOptimizer',
    'AsyncProcessor',
    'CompressionMiddleware',
    'BatchProcessor',
    'MemoryOptimizer'
]