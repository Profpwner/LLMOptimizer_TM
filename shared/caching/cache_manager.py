"""
Central cache management system coordinating all cache layers.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheLayer(Enum):
    """Cache layer hierarchy."""
    CDN = "cdn"  # CloudFront/Cloudflare
    REDIS = "redis"  # Redis distributed cache
    APPLICATION = "application"  # In-memory application cache
    LOCAL = "local"  # Local process cache


@dataclass
class CacheConfig:
    """Global cache configuration."""
    default_ttl: int = 300  # 5 minutes
    max_cache_size_mb: int = 1024  # 1GB
    enable_compression: bool = True
    enable_metrics: bool = True
    namespace: str = "llmoptimizer"
    
    # Layer-specific configs
    cdn_enabled: bool = True
    redis_enabled: bool = True
    application_enabled: bool = True
    local_enabled: bool = True
    
    # Cache warming
    enable_warming: bool = True
    warming_interval: int = 300  # 5 minutes
    
    # Invalidation
    enable_invalidation_events: bool = True
    invalidation_batch_size: int = 100


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheManager:
    """
    Manages multi-layer caching system for 100K+ concurrent users.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.layers: Dict[CacheLayer, Any] = {}
        self.stats: Dict[CacheLayer, CacheStats] = {
            layer: CacheStats() for layer in CacheLayer
        }
        
        # Cache warming registry
        self.warming_functions: Dict[str, Callable] = {}
        self.warming_task: Optional[asyncio.Task] = None
        
        # Invalidation callbacks
        self.invalidation_callbacks: List[Callable] = []
        
        # Metrics collection
        self.metrics_task: Optional[asyncio.Task] = None
    
    def register_layer(self, layer: CacheLayer, cache_instance: Any):
        """Register a cache layer implementation."""
        self.layers[layer] = cache_instance
        logger.info(f"Registered cache layer: {layer.value}")
    
    async def initialize(self):
        """Initialize all cache layers."""
        # Initialize each registered layer
        for layer, instance in self.layers.items():
            if hasattr(instance, 'initialize'):
                await instance.initialize()
        
        # Start background tasks
        if self.config.enable_warming:
            self.warming_task = asyncio.create_task(self._cache_warming_loop())
        
        if self.config.enable_metrics:
            self.metrics_task = asyncio.create_task(self._metrics_collection_loop())
        
        logger.info("Cache manager initialized")
    
    async def shutdown(self):
        """Shutdown cache manager and all layers."""
        # Cancel background tasks
        if self.warming_task:
            self.warming_task.cancel()
        if self.metrics_task:
            self.metrics_task.cancel()
        
        # Shutdown each layer
        for layer, instance in self.layers.items():
            if hasattr(instance, 'shutdown'):
                await instance.shutdown()
        
        logger.info("Cache manager shutdown complete")
    
    def generate_key(self, *args, namespace: Optional[str] = None) -> str:
        """Generate cache key from arguments."""
        key_parts = [namespace or self.config.namespace]
        
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True))
            else:
                key_parts.append(str(arg))
        
        key_string = ":".join(key_parts)
        
        # Use hash for long keys
        if len(key_string) > 250:
            key_hash = hashlib.sha256(key_string.encode()).hexdigest()
            return f"{key_parts[0]}:hash:{key_hash}"
        
        return key_string
    
    async def get(
        self,
        key: str,
        layers: Optional[List[CacheLayer]] = None
    ) -> Optional[Any]:
        """
        Get value from cache, checking layers in order.
        """
        layers = layers or list(CacheLayer)
        
        for layer in layers:
            if layer not in self.layers:
                continue
            
            try:
                cache = self.layers[layer]
                value = await self._get_from_layer(cache, key)
                
                if value is not None:
                    self.stats[layer].hits += 1
                    
                    # Populate higher layers if missing
                    await self._populate_higher_layers(key, value, layer, layers)
                    
                    return value
                else:
                    self.stats[layer].misses += 1
                    
            except Exception as e:
                self.stats[layer].errors += 1
                logger.error(f"Cache get error in {layer.value}: {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        layers: Optional[List[CacheLayer]] = None
    ):
        """
        Set value in specified cache layers.
        """
        layers = layers or list(CacheLayer)
        ttl = ttl or self.config.default_ttl
        
        # Set in all specified layers concurrently
        tasks = []
        for layer in layers:
            if layer not in self.layers:
                continue
            
            cache = self.layers[layer]
            task = self._set_in_layer(cache, key, value, ttl, layer)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def delete(
        self,
        key: str,
        layers: Optional[List[CacheLayer]] = None
    ):
        """
        Delete value from specified cache layers.
        """
        layers = layers or list(CacheLayer)
        
        # Delete from all layers concurrently
        tasks = []
        for layer in layers:
            if layer not in self.layers:
                continue
            
            cache = self.layers[layer]
            task = self._delete_from_layer(cache, key, layer)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Trigger invalidation callbacks
        if self.config.enable_invalidation_events:
            await self._trigger_invalidation_callbacks(key)
    
    async def clear(self, layers: Optional[List[CacheLayer]] = None):
        """
        Clear all values from specified cache layers.
        """
        layers = layers or list(CacheLayer)
        
        for layer in layers:
            if layer not in self.layers:
                continue
            
            try:
                cache = self.layers[layer]
                if hasattr(cache, 'clear'):
                    await cache.clear()
                logger.info(f"Cleared cache layer: {layer.value}")
            except Exception as e:
                logger.error(f"Failed to clear {layer.value}: {e}")
    
    async def _get_from_layer(self, cache: Any, key: str) -> Optional[Any]:
        """Get value from specific cache layer."""
        if hasattr(cache, 'get'):
            if asyncio.iscoroutinefunction(cache.get):
                return await cache.get(key)
            else:
                return cache.get(key)
        return None
    
    async def _set_in_layer(
        self,
        cache: Any,
        key: str,
        value: Any,
        ttl: int,
        layer: CacheLayer
    ):
        """Set value in specific cache layer."""
        try:
            if hasattr(cache, 'set'):
                if asyncio.iscoroutinefunction(cache.set):
                    await cache.set(key, value, ttl)
                else:
                    cache.set(key, value, ttl)
            
            self.stats[layer].sets += 1
        except Exception as e:
            self.stats[layer].errors += 1
            logger.error(f"Cache set error in {layer.value}: {e}")
    
    async def _delete_from_layer(self, cache: Any, key: str, layer: CacheLayer):
        """Delete value from specific cache layer."""
        try:
            if hasattr(cache, 'delete'):
                if asyncio.iscoroutinefunction(cache.delete):
                    await cache.delete(key)
                else:
                    cache.delete(key)
            
            self.stats[layer].deletes += 1
        except Exception as e:
            self.stats[layer].errors += 1
            logger.error(f"Cache delete error in {layer.value}: {e}")
    
    async def _populate_higher_layers(
        self,
        key: str,
        value: Any,
        found_layer: CacheLayer,
        layers: List[CacheLayer]
    ):
        """Populate cache value in higher layers."""
        found_index = layers.index(found_layer)
        higher_layers = layers[:found_index]
        
        if higher_layers:
            await self.set(key, value, layers=higher_layers)
    
    def register_warming_function(self, key_pattern: str, func: Callable):
        """Register a function for cache warming."""
        self.warming_functions[key_pattern] = func
        logger.info(f"Registered warming function for pattern: {key_pattern}")
    
    async def _cache_warming_loop(self):
        """Background task for cache warming."""
        while True:
            try:
                await asyncio.sleep(self.config.warming_interval)
                await self._warm_caches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache warming error: {e}")
    
    async def _warm_caches(self):
        """Execute cache warming functions."""
        tasks = []
        
        for pattern, func in self.warming_functions.items():
            if asyncio.iscoroutinefunction(func):
                task = func()
            else:
                task = asyncio.get_event_loop().run_in_executor(None, func)
            
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"Cache warming completed: {success_count}/{len(tasks)} successful")
    
    def register_invalidation_callback(self, callback: Callable):
        """Register callback for cache invalidation events."""
        self.invalidation_callbacks.append(callback)
    
    async def _trigger_invalidation_callbacks(self, key: str):
        """Trigger invalidation callbacks."""
        for callback in self.invalidation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(key)
                else:
                    callback(key)
            except Exception as e:
                logger.error(f"Invalidation callback error: {e}")
    
    async def _metrics_collection_loop(self):
        """Background task for metrics collection."""
        while True:
            try:
                await asyncio.sleep(60)  # Collect every minute
                metrics = self.get_metrics()
                logger.info(f"Cache metrics: {json.dumps(metrics, indent=2)}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics for all layers."""
        metrics = {
            'layers': {},
            'total_hits': 0,
            'total_misses': 0,
            'overall_hit_rate': 0.0
        }
        
        total_hits = 0
        total_misses = 0
        
        for layer, stats in self.stats.items():
            metrics['layers'][layer.value] = {
                'hits': stats.hits,
                'misses': stats.misses,
                'hit_rate': stats.hit_rate,
                'sets': stats.sets,
                'deletes': stats.deletes,
                'errors': stats.errors
            }
            
            total_hits += stats.hits
            total_misses += stats.misses
        
        metrics['total_hits'] = total_hits
        metrics['total_misses'] = total_misses
        
        if total_hits + total_misses > 0:
            metrics['overall_hit_rate'] = total_hits / (total_hits + total_misses)
        
        return metrics
    
    async def batch_get(
        self,
        keys: List[str],
        layers: Optional[List[CacheLayer]] = None
    ) -> Dict[str, Any]:
        """Get multiple values from cache."""
        results = {}
        
        # Try to get all keys from each layer
        for layer in (layers or list(CacheLayer)):
            if layer not in self.layers:
                continue
            
            cache = self.layers[layer]
            
            # Check if cache supports batch operations
            if hasattr(cache, 'mget'):
                try:
                    if asyncio.iscoroutinefunction(cache.mget):
                        layer_results = await cache.mget(keys)
                    else:
                        layer_results = cache.mget(keys)
                    
                    # Merge results
                    for key, value in layer_results.items():
                        if key not in results and value is not None:
                            results[key] = value
                            
                except Exception as e:
                    logger.error(f"Batch get error in {layer.value}: {e}")
            else:
                # Fall back to individual gets
                for key in keys:
                    if key not in results:
                        value = await self._get_from_layer(cache, key)
                        if value is not None:
                            results[key] = value
        
        return results
    
    async def batch_set(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
        layers: Optional[List[CacheLayer]] = None
    ):
        """Set multiple values in cache."""
        ttl = ttl or self.config.default_ttl
        layers = layers or list(CacheLayer)
        
        for layer in layers:
            if layer not in self.layers:
                continue
            
            cache = self.layers[layer]
            
            # Check if cache supports batch operations
            if hasattr(cache, 'mset'):
                try:
                    if asyncio.iscoroutinefunction(cache.mset):
                        await cache.mset(items, ttl)
                    else:
                        cache.mset(items, ttl)
                except Exception as e:
                    logger.error(f"Batch set error in {layer.value}: {e}")
            else:
                # Fall back to individual sets
                tasks = [
                    self._set_in_layer(cache, key, value, ttl, layer)
                    for key, value in items.items()
                ]
                await asyncio.gather(*tasks, return_exceptions=True)