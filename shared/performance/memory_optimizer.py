"""
Memory optimization utilities for handling 100K+ concurrent users.
"""

import gc
import sys
import weakref
import asyncio
import psutil
import resource
from typing import Any, Dict, List, Optional, Set, TypeVar, Callable
from dataclasses import dataclass
import time
import logging
from functools import lru_cache, wraps
from collections import OrderedDict
import tracemalloc

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class MemoryMetrics:
    """Memory usage metrics."""
    rss: int  # Resident Set Size
    vms: int  # Virtual Memory Size
    shared: int  # Shared memory
    available: int  # Available system memory
    percent: float  # Memory usage percentage
    gc_stats: Dict[str, Any]
    object_counts: Dict[str, int]


class MemoryOptimizer:
    """
    Memory optimization manager for high-concurrency applications.
    """
    
    def __init__(
        self,
        target_memory_mb: int = 4096,
        gc_threshold: float = 0.8,
        enable_profiling: bool = False
    ):
        self.target_memory_mb = target_memory_mb
        self.gc_threshold = gc_threshold
        self.enable_profiling = enable_profiling
        
        # Object pools
        self.object_pools: Dict[type, List[Any]] = {}
        self.pool_sizes: Dict[type, int] = {}
        
        # Weak references for large objects
        self.weak_refs: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        
        # Memory monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.memory_warnings: List[Dict[str, Any]] = []
        
        # Set up memory profiling
        if self.enable_profiling:
            tracemalloc.start()
        
        # Configure garbage collection
        self._configure_gc()
    
    def _configure_gc(self):
        """Configure garbage collection for optimal performance."""
        # Set GC thresholds for better performance with many objects
        gc.set_threshold(700, 10, 10)
        
        # Enable GC stats
        gc.set_debug(gc.DEBUG_STATS)
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start memory monitoring task."""
        self.monitoring_task = asyncio.create_task(
            self._monitor_memory(interval)
        )
        logger.info("Memory monitoring started")
    
    async def stop_monitoring(self):
        """Stop memory monitoring."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self.enable_profiling:
            tracemalloc.stop()
    
    async def _monitor_memory(self, interval: float):
        """Monitor memory usage and trigger optimization if needed."""
        while True:
            try:
                metrics = self.get_memory_metrics()
                
                # Check if we're approaching memory limit
                memory_usage_mb = metrics.rss / (1024 * 1024)
                usage_ratio = memory_usage_mb / self.target_memory_mb
                
                if usage_ratio > self.gc_threshold:
                    await self._optimize_memory(metrics)
                
                # Log metrics
                logger.debug(
                    f"Memory usage: {memory_usage_mb:.1f}MB / {self.target_memory_mb}MB "
                    f"({usage_ratio * 100:.1f}%)"
                )
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def get_memory_metrics(self) -> MemoryMetrics:
        """Get current memory metrics."""
        process = psutil.Process()
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        
        # Get GC stats
        gc_stats = {
            f"generation_{i}": {
                "collections": gc.get_stats()[i].get('collections', 0),
                "collected": gc.get_stats()[i].get('collected', 0),
                "uncollectable": gc.get_stats()[i].get('uncollectable', 0)
            }
            for i in range(gc.get_count().__len__())
        }
        
        # Get object counts by type
        object_counts = {}
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            object_counts[obj_type] = object_counts.get(obj_type, 0) + 1
        
        # Get top 10 object types by count
        top_objects = dict(
            sorted(object_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        return MemoryMetrics(
            rss=memory_info.rss,
            vms=memory_info.vms,
            shared=getattr(memory_info, 'shared', 0),
            available=system_memory.available,
            percent=process.memory_percent(),
            gc_stats=gc_stats,
            object_counts=top_objects
        )
    
    async def _optimize_memory(self, metrics: MemoryMetrics):
        """Perform memory optimization."""
        logger.warning(f"Memory usage high: {metrics.percent:.1f}%. Optimizing...")
        
        # Record warning
        self.memory_warnings.append({
            'timestamp': time.time(),
            'metrics': metrics,
            'action': 'optimization'
        })
        
        # Force garbage collection
        gc.collect()
        
        # Clear object pools that are too large
        self._optimize_object_pools()
        
        # Clear weak references
        self.weak_refs.clear()
        
        # If still high, take more aggressive action
        if metrics.percent > 90:
            await self._aggressive_memory_cleanup()
    
    def _optimize_object_pools(self):
        """Optimize object pools by clearing oversized pools."""
        for obj_type, pool in self.object_pools.items():
            max_size = self.pool_sizes.get(obj_type, 100)
            
            if len(pool) > max_size * 2:
                # Keep only max_size objects
                self.object_pools[obj_type] = pool[:max_size]
                logger.info(f"Reduced {obj_type.__name__} pool from {len(pool)} to {max_size}")
    
    async def _aggressive_memory_cleanup(self):
        """Perform aggressive memory cleanup."""
        logger.warning("Performing aggressive memory cleanup")
        
        # Clear all caches
        for obj in gc.get_objects():
            if isinstance(obj, dict) and hasattr(obj, 'clear'):
                # Clear LRU caches
                if hasattr(obj, 'cache_clear'):
                    obj.cache_clear()
        
        # Clear all object pools
        self.object_pools.clear()
        
        # Force multiple GC cycles
        for _ in range(3):
            gc.collect()
    
    def create_object_pool(self, obj_type: type, size: int = 100) -> 'ObjectPool':
        """Create an object pool for a specific type."""
        pool = ObjectPool(obj_type, size, self)
        self.object_pools[obj_type] = []
        self.pool_sizes[obj_type] = size
        return pool
    
    def get_memory_profile(self) -> Optional[Dict[str, Any]]:
        """Get memory allocation profile if profiling is enabled."""
        if not self.enable_profiling:
            return None
        
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        profile = {
            'top_allocations': [
                {
                    'file': stat.traceback.format()[0],
                    'size': stat.size,
                    'count': stat.count
                }
                for stat in top_stats[:20]
            ],
            'total_size': sum(stat.size for stat in top_stats),
            'total_count': sum(stat.count for stat in top_stats)
        }
        
        return profile
    
    def store_weak_ref(self, key: str, obj: Any):
        """Store a weak reference to an object."""
        self.weak_refs[key] = obj
    
    def get_weak_ref(self, key: str) -> Optional[Any]:
        """Get object from weak reference if still alive."""
        return self.weak_refs.get(key)


class ObjectPool:
    """
    Object pool for reusing objects and reducing memory allocation.
    """
    
    def __init__(self, obj_type: type, size: int, optimizer: MemoryOptimizer):
        self.obj_type = obj_type
        self.size = size
        self.optimizer = optimizer
        self.pool: List[Any] = []
        self.in_use: Set[int] = set()
    
    def acquire(self, *args, **kwargs) -> Any:
        """Acquire an object from the pool."""
        # Try to get from pool
        if self.pool:
            obj = self.pool.pop()
            
            # Reset object if it has a reset method
            if hasattr(obj, 'reset'):
                obj.reset()
            
            self.in_use.add(id(obj))
            return obj
        
        # Create new object
        obj = self.obj_type(*args, **kwargs)
        self.in_use.add(id(obj))
        
        # Store in optimizer's pool tracking
        if self.obj_type in self.optimizer.object_pools:
            self.optimizer.object_pools[self.obj_type].append(obj)
        
        return obj
    
    def release(self, obj: Any):
        """Release object back to pool."""
        obj_id = id(obj)
        
        if obj_id not in self.in_use:
            return
        
        self.in_use.remove(obj_id)
        
        # Add back to pool if not full
        if len(self.pool) < self.size:
            self.pool.append(obj)
        else:
            # Let GC handle it
            pass


class MemoryEfficientCache:
    """
    Memory-efficient LRU cache with size limits.
    """
    
    def __init__(self, maxsize: int = 1000, max_memory_mb: int = 100):
        self.maxsize = maxsize
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict = OrderedDict()
        self.memory_usage = 0
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        if key in self.cache:
            self.hits += 1
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        
        self.misses += 1
        return None
    
    def put(self, key: str, value: Any):
        """Put item in cache."""
        # Estimate memory usage
        size = sys.getsizeof(value)
        
        # Check if we need to evict items
        while (
            (len(self.cache) >= self.maxsize or 
             self.memory_usage + size > self.max_memory_bytes) and
            self.cache
        ):
            # Remove least recently used
            evicted_key, evicted_value = self.cache.popitem(last=False)
            self.memory_usage -= sys.getsizeof(evicted_value)
        
        # Add new item
        self.cache[key] = value
        self.memory_usage += size
    
    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        self.memory_usage = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        
        return {
            'size': len(self.cache),
            'memory_usage_mb': self.memory_usage / (1024 * 1024),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }


def memory_limit(max_memory_mb: int):
    """Decorator to limit memory usage of a function."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Set memory limit
            resource.setrlimit(
                resource.RLIMIT_AS,
                (max_memory_mb * 1024 * 1024, resource.RLIM_INFINITY)
            )
            
            try:
                return await func(*args, **kwargs)
            finally:
                # Reset limit
                resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Set memory limit
            resource.setrlimit(
                resource.RLIMIT_AS,
                (max_memory_mb * 1024 * 1024, resource.RLIM_INFINITY)
            )
            
            try:
                return func(*args, **kwargs)
            finally:
                # Reset limit
                resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Memory-efficient data structures
class ChunkedList:
    """List that stores data in chunks to reduce memory overhead."""
    
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size
        self.chunks: List[List[Any]] = []
        self.size = 0
    
    def append(self, item: Any):
        """Append item to list."""
        if not self.chunks or len(self.chunks[-1]) >= self.chunk_size:
            self.chunks.append([])
        
        self.chunks[-1].append(item)
        self.size += 1
    
    def __getitem__(self, index: int) -> Any:
        """Get item by index."""
        if index < 0 or index >= self.size:
            raise IndexError("Index out of range")
        
        chunk_idx = index // self.chunk_size
        item_idx = index % self.chunk_size
        
        return self.chunks[chunk_idx][item_idx]
    
    def __len__(self) -> int:
        """Get list length."""
        return self.size
    
    def clear(self):
        """Clear the list."""
        self.chunks.clear()
        self.size = 0


# Global memory optimizer instance
memory_optimizer = MemoryOptimizer()


async def optimize_for_high_memory_load():
    """Optimize application for high memory load scenarios."""
    # Start memory monitoring
    await memory_optimizer.start_monitoring(interval=10.0)
    
    # Configure system limits
    try:
        # Increase file descriptor limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))
        
        # Set max memory usage (8GB)
        resource.setrlimit(
            resource.RLIMIT_AS,
            (8 * 1024 * 1024 * 1024, resource.RLIM_INFINITY)
        )
    except Exception as e:
        logger.warning(f"Failed to set resource limits: {e}")
    
    logger.info("Memory optimization configured for high load")