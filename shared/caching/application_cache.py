"""
Application-level in-memory caching with advanced features.
"""

import asyncio
import time
import weakref
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
import sys
import heapq
import threading
import logging
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    size: int
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    cost: float = 1.0  # For cost-based eviction
    tags: Set[str] = field(default_factory=set)


class EvictionPolicy:
    """Base class for cache eviction policies."""
    
    def should_evict(self, cache: 'ApplicationCache') -> bool:
        """Check if eviction is needed."""
        raise NotImplementedError
    
    def select_victim(self, cache: 'ApplicationCache') -> Optional[str]:
        """Select entry to evict."""
        raise NotImplementedError


class LRUEviction(EvictionPolicy):
    """Least Recently Used eviction policy."""
    
    def should_evict(self, cache: 'ApplicationCache') -> bool:
        return (
            len(cache.entries) >= cache.max_entries or
            cache.current_size >= cache.max_size
        )
    
    def select_victim(self, cache: 'ApplicationCache') -> Optional[str]:
        if not cache.access_order:
            return None
        
        # Get least recently used key
        for key in cache.access_order:
            if key in cache.entries:
                return key
        
        return None


class LFUEviction(EvictionPolicy):
    """Least Frequently Used eviction policy."""
    
    def should_evict(self, cache: 'ApplicationCache') -> bool:
        return (
            len(cache.entries) >= cache.max_entries or
            cache.current_size >= cache.max_size
        )
    
    def select_victim(self, cache: 'ApplicationCache') -> Optional[str]:
        if not cache.entries:
            return None
        
        # Find entry with lowest access count
        min_count = float('inf')
        victim_key = None
        
        for key, entry in cache.entries.items():
            if entry.access_count < min_count:
                min_count = entry.access_count
                victim_key = key
        
        return victim_key


class FIFOEviction(EvictionPolicy):
    """First In First Out eviction policy."""
    
    def should_evict(self, cache: 'ApplicationCache') -> bool:
        return (
            len(cache.entries) >= cache.max_entries or
            cache.current_size >= cache.max_size
        )
    
    def select_victim(self, cache: 'ApplicationCache') -> Optional[str]:
        if not cache.entries:
            return None
        
        # Find oldest entry
        oldest_time = float('inf')
        victim_key = None
        
        for key, entry in cache.entries.items():
            if entry.created_at < oldest_time:
                oldest_time = entry.created_at
                victim_key = key
        
        return victim_key


class AdaptiveEviction(EvictionPolicy):
    """Adaptive eviction policy that combines multiple strategies."""
    
    def __init__(self):
        self.lru_weight = 0.5
        self.lfu_weight = 0.3
        self.size_weight = 0.2
    
    def should_evict(self, cache: 'ApplicationCache') -> bool:
        return (
            len(cache.entries) >= cache.max_entries or
            cache.current_size >= cache.max_size
        )
    
    def select_victim(self, cache: 'ApplicationCache') -> Optional[str]:
        if not cache.entries:
            return None
        
        # Calculate score for each entry
        scores = {}
        current_time = time.time()
        
        for key, entry in cache.entries.items():
            # LRU component (time since last access)
            lru_score = current_time - entry.last_accessed
            
            # LFU component (inverse of access count)
            lfu_score = 1.0 / (entry.access_count + 1)
            
            # Size component (larger items get higher score)
            size_score = entry.size / cache.max_size
            
            # Combined score (higher score = more likely to evict)
            scores[key] = (
                self.lru_weight * lru_score +
                self.lfu_weight * lfu_score +
                self.size_weight * size_score
            )
        
        # Select entry with highest score
        return max(scores.items(), key=lambda x: x[1])[0]


class ApplicationCache:
    """
    High-performance application-level cache with multiple eviction policies.
    """
    
    def __init__(
        self,
        max_size: int = 1024 * 1024 * 1024,  # 1GB
        max_entries: int = 100000,
        default_ttl: int = 3600,
        eviction_policy: Optional[EvictionPolicy] = None,
        enable_stats: bool = True
    ):
        self.max_size = max_size
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        
        # Cache storage
        self.entries: Dict[str, CacheEntry] = {}
        self.access_order: OrderedDict = OrderedDict()
        self.current_size = 0
        
        # Eviction policy
        self.eviction_policy = eviction_policy or LRUEviction()
        
        # TTL management
        self.expiry_heap: List[Tuple[float, str]] = []
        self.expiry_task: Optional[asyncio.Task] = None
        
        # Tags for grouped invalidation
        self.tag_index: Dict[str, Set[str]] = {}
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0,
            'expirations': 0,
            'errors': 0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Weak references for large objects
        self.weak_refs: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
    
    async def start(self):
        """Start background tasks."""
        self.expiry_task = asyncio.create_task(self._expiry_cleaner())
        logger.info("Application cache started")
    
    async def stop(self):
        """Stop background tasks."""
        if self.expiry_task:
            self.expiry_task.cancel()
            try:
                await self.expiry_task
            except asyncio.CancelledError:
                pass
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of value."""
        return sys.getsizeof(value)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            entry = self.entries.get(key)
            
            if entry is None:
                self.stats['misses'] += 1
                return None
            
            # Check expiration
            if entry.expires_at <= time.time():
                self._remove_entry(key)
                self.stats['expirations'] += 1
                self.stats['misses'] += 1
                return None
            
            # Update access metadata
            entry.access_count += 1
            entry.last_accessed = time.time()
            
            # Update LRU order
            self.access_order.move_to_end(key)
            
            self.stats['hits'] += 1
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        cost: float = 1.0,
        tags: Optional[Set[str]] = None
    ) -> bool:
        """Set value in cache."""
        ttl = ttl or self.default_ttl
        size = self._estimate_size(value)
        
        # Check if value is too large
        if size > self.max_size:
            logger.warning(f"Value too large for cache: {size} bytes")
            return False
        
        with self.lock:
            # Remove existing entry if present
            if key in self.entries:
                self._remove_entry(key)
            
            # Evict entries if needed
            while self.eviction_policy.should_evict(self):
                victim = self.eviction_policy.select_victim(self)
                if victim:
                    self._remove_entry(victim)
                    self.stats['evictions'] += 1
                else:
                    break
            
            # Create new entry
            expires_at = time.time() + ttl
            entry = CacheEntry(
                key=key,
                value=value,
                size=size,
                created_at=time.time(),
                expires_at=expires_at,
                cost=cost,
                tags=tags or set()
            )
            
            # Store entry
            self.entries[key] = entry
            self.access_order[key] = None
            self.current_size += size
            
            # Add to expiry heap
            heapq.heappush(self.expiry_heap, (expires_at, key))
            
            # Update tag index
            for tag in entry.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = set()
                self.tag_index[tag].add(key)
            
            # Store weak reference for large objects
            if size > self.max_size * 0.1:  # 10% of max size
                self.weak_refs[key] = value
            
            self.stats['sets'] += 1
            return True
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        with self.lock:
            if key in self.entries:
                self._remove_entry(key)
                return True
            return False
    
    def _remove_entry(self, key: str):
        """Remove entry from cache."""
        if key not in self.entries:
            return
        
        entry = self.entries[key]
        
        # Update size
        self.current_size -= entry.size
        
        # Remove from storage
        del self.entries[key]
        self.access_order.pop(key, None)
        
        # Remove from tag index
        for tag in entry.tags:
            if tag in self.tag_index:
                self.tag_index[tag].discard(key)
                if not self.tag_index[tag]:
                    del self.tag_index[tag]
        
        # Remove weak reference
        self.weak_refs.pop(key, None)
    
    def clear(self):
        """Clear all entries from cache."""
        with self.lock:
            self.entries.clear()
            self.access_order.clear()
            self.expiry_heap.clear()
            self.tag_index.clear()
            self.weak_refs.clear()
            self.current_size = 0
    
    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        with self.lock:
            if tag not in self.tag_index:
                return 0
            
            keys_to_remove = list(self.tag_index[tag])
            for key in keys_to_remove:
                self._remove_entry(key)
            
            return len(keys_to_remove)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate entries matching key pattern."""
        import fnmatch
        
        with self.lock:
            keys_to_remove = [
                key for key in self.entries
                if fnmatch.fnmatch(key, pattern)
            ]
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            return len(keys_to_remove)
    
    async def _expiry_cleaner(self):
        """Background task to clean expired entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = time.time()
                expired_keys = []
                
                with self.lock:
                    # Find expired entries
                    while self.expiry_heap and self.expiry_heap[0][0] <= current_time:
                        _, key = heapq.heappop(self.expiry_heap)
                        
                        # Verify entry still exists and is expired
                        entry = self.entries.get(key)
                        if entry and entry.expires_at <= current_time:
                            expired_keys.append(key)
                    
                    # Remove expired entries
                    for key in expired_keys:
                        self._remove_entry(key)
                        self.stats['expirations'] += 1
                
                if expired_keys:
                    logger.info(f"Cleaned {len(expired_keys)} expired cache entries")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Expiry cleaner error: {e}")
                self.stats['errors'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            hit_rate = (
                self.stats['hits'] / (self.stats['hits'] + self.stats['misses'])
                if (self.stats['hits'] + self.stats['misses']) > 0
                else 0.0
            )
            
            return {
                **self.stats,
                'hit_rate': hit_rate,
                'current_entries': len(self.entries),
                'current_size_mb': self.current_size / (1024 * 1024),
                'max_size_mb': self.max_size / (1024 * 1024),
                'utilization': self.current_size / self.max_size if self.max_size > 0 else 0
            }
    
    def warm_cache(self, items: Dict[str, Any], ttl: Optional[int] = None):
        """Pre-populate cache with items."""
        success_count = 0
        
        for key, value in items.items():
            if self.set(key, value, ttl):
                success_count += 1
        
        logger.info(f"Warmed cache with {success_count}/{len(items)} items")
        return success_count


# Decorators for caching
def cached(
    ttl: int = 300,
    key_func: Optional[Callable] = None,
    tags: Optional[Set[str]] = None
):
    """Decorator for caching function results."""
    def decorator(func):
        # Create cache instance for this function
        cache = ApplicationCache(
            max_size=100 * 1024 * 1024,  # 100MB per function
            max_entries=10000
        )
        
        # Start cache in background
        asyncio.create_task(cache.start())
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl=ttl, tags=tags)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl=ttl, tags=tags)
            
            return result
        
        # Add cache control methods
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.cache = cache
        wrapper.invalidate = lambda: cache.clear()
        wrapper.stats = lambda: cache.get_stats()
        
        return wrapper
    
    return decorator


# Pre-configured cache instances
def create_api_cache() -> ApplicationCache:
    """Create cache optimized for API responses."""
    return ApplicationCache(
        max_size=512 * 1024 * 1024,  # 512MB
        max_entries=50000,
        default_ttl=300,  # 5 minutes
        eviction_policy=AdaptiveEviction()
    )


def create_session_cache() -> ApplicationCache:
    """Create cache optimized for user sessions."""
    return ApplicationCache(
        max_size=256 * 1024 * 1024,  # 256MB
        max_entries=100000,  # 100K concurrent users
        default_ttl=3600,  # 1 hour
        eviction_policy=LRUEviction()
    )


def create_computation_cache() -> ApplicationCache:
    """Create cache optimized for expensive computations."""
    return ApplicationCache(
        max_size=1024 * 1024 * 1024,  # 1GB
        max_entries=10000,
        default_ttl=86400,  # 1 day
        eviction_policy=LFUEviction()
    )