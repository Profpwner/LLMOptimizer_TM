"""
Cache invalidation strategies and patterns.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Set, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


class InvalidationStrategy(Enum):
    """Cache invalidation strategies."""
    IMMEDIATE = "immediate"  # Invalidate immediately
    DELAYED = "delayed"  # Invalidate after delay
    SCHEDULED = "scheduled"  # Invalidate at specific time
    CASCADE = "cascade"  # Invalidate related entries
    PATTERN = "pattern"  # Invalidate by pattern matching
    TAG = "tag"  # Invalidate by tags
    TTL = "ttl"  # Time-based expiration
    EVENT = "event"  # Event-driven invalidation
    HYBRID = "hybrid"  # Combination of strategies


@dataclass
class InvalidationRule:
    """Rule for cache invalidation."""
    strategy: InvalidationStrategy
    target: str  # Key, pattern, or tag
    delay: Optional[float] = None
    scheduled_time: Optional[datetime] = None
    cascade_targets: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InvalidationEvent:
    """Event that triggers cache invalidation."""
    event_type: str
    source: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    affected_keys: List[str] = field(default_factory=list)
    affected_tags: List[str] = field(default_factory=list)


class CacheInvalidator:
    """
    Advanced cache invalidation manager for 100K+ concurrent users.
    """
    
    def __init__(self, cache_manager: Any):
        self.cache_manager = cache_manager
        
        # Invalidation rules
        self.rules: List[InvalidationRule] = []
        self.rule_index: Dict[str, List[InvalidationRule]] = {}
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Scheduled invalidations
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        
        # Invalidation queue for batching
        self.invalidation_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.batch_processor_task: Optional[asyncio.Task] = None
        
        # Dependencies graph
        self.dependencies: Dict[str, Set[str]] = {}
        self.reverse_dependencies: Dict[str, Set[str]] = {}
        
        # Metrics
        self.metrics = {
            'total_invalidations': 0,
            'immediate_invalidations': 0,
            'delayed_invalidations': 0,
            'cascade_invalidations': 0,
            'pattern_invalidations': 0,
            'tag_invalidations': 0,
            'event_invalidations': 0,
            'failed_invalidations': 0
        }
    
    async def start(self):
        """Start invalidation processor."""
        self.batch_processor_task = asyncio.create_task(self._batch_processor())
        logger.info("Cache invalidator started")
    
    async def stop(self):
        """Stop invalidation processor."""
        # Cancel scheduled tasks
        for task in self.scheduled_tasks.values():
            task.cancel()
        
        # Stop batch processor
        if self.batch_processor_task:
            self.batch_processor_task.cancel()
            try:
                await self.batch_processor_task
            except asyncio.CancelledError:
                pass
    
    def add_rule(self, rule: InvalidationRule):
        """Add invalidation rule."""
        self.rules.append(rule)
        
        # Index by strategy
        if rule.strategy not in self.rule_index:
            self.rule_index[rule.strategy] = []
        self.rule_index[rule.strategy].append(rule)
        
        # Sort rules by priority
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        
        logger.info(f"Added invalidation rule: {rule.strategy.value} for {rule.target}")
    
    def add_dependency(self, key: str, depends_on: List[str]):
        """Add cache key dependencies."""
        if key not in self.dependencies:
            self.dependencies[key] = set()
        
        self.dependencies[key].update(depends_on)
        
        # Update reverse dependencies
        for dep in depends_on:
            if dep not in self.reverse_dependencies:
                self.reverse_dependencies[dep] = set()
            self.reverse_dependencies[dep].add(key)
    
    async def invalidate(
        self,
        keys: Optional[Union[str, List[str]]] = None,
        tags: Optional[Union[str, List[str]]] = None,
        pattern: Optional[str] = None,
        strategy: InvalidationStrategy = InvalidationStrategy.IMMEDIATE,
        cascade: bool = True
    ):
        """
        Invalidate cache entries using specified strategy.
        """
        # Normalize inputs
        if isinstance(keys, str):
            keys = [keys]
        if isinstance(tags, str):
            tags = [tags]
        
        # Create invalidation event
        event = InvalidationEvent(
            event_type="manual_invalidation",
            source="api",
            affected_keys=keys or [],
            affected_tags=tags or [],
            data={"pattern": pattern, "cascade": cascade}
        )
        
        # Route to appropriate handler
        if strategy == InvalidationStrategy.IMMEDIATE:
            await self._invalidate_immediate(event)
        elif strategy == InvalidationStrategy.DELAYED:
            await self._invalidate_delayed(event, delay=5.0)
        elif strategy == InvalidationStrategy.CASCADE:
            await self._invalidate_cascade(event)
        elif strategy == InvalidationStrategy.PATTERN:
            await self._invalidate_pattern(pattern or "*")
        elif strategy == InvalidationStrategy.TAG:
            await self._invalidate_tags(tags or [])
        else:
            logger.warning(f"Unsupported invalidation strategy: {strategy}")
    
    async def _invalidate_immediate(self, event: InvalidationEvent):
        """Immediately invalidate cache entries."""
        try:
            # Invalidate keys
            if event.affected_keys:
                await self.cache_manager.delete(event.affected_keys)
                self.metrics['immediate_invalidations'] += len(event.affected_keys)
            
            # Invalidate tags
            if event.affected_tags:
                for tag in event.affected_tags:
                    await self._invalidate_tag(tag)
            
            self.metrics['total_invalidations'] += 1
            
        except Exception as e:
            logger.error(f"Immediate invalidation error: {e}")
            self.metrics['failed_invalidations'] += 1
    
    async def _invalidate_delayed(self, event: InvalidationEvent, delay: float):
        """Invalidate cache entries after delay."""
        async def delayed_invalidation():
            await asyncio.sleep(delay)
            await self._invalidate_immediate(event)
            self.metrics['delayed_invalidations'] += 1
        
        task = asyncio.create_task(delayed_invalidation())
        task_id = f"delayed_{time.time()}"
        self.scheduled_tasks[task_id] = task
    
    async def _invalidate_cascade(self, event: InvalidationEvent):
        """Invalidate cache entries and their dependencies."""
        invalidated = set()
        to_process = set(event.affected_keys)
        
        while to_process:
            key = to_process.pop()
            if key in invalidated:
                continue
            
            # Invalidate the key
            await self.cache_manager.delete(key)
            invalidated.add(key)
            
            # Add reverse dependencies
            if key in self.reverse_dependencies:
                to_process.update(self.reverse_dependencies[key])
        
        self.metrics['cascade_invalidations'] += len(invalidated)
        self.metrics['total_invalidations'] += 1
        
        logger.info(f"Cascade invalidation: {len(invalidated)} entries")
    
    async def _invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        # Convert glob pattern to regex
        regex_pattern = self._glob_to_regex(pattern)
        
        # Get all cache keys (this should be optimized for production)
        # In production, use cache backend that supports pattern operations
        invalidated_count = 0
        
        # For Redis-backed cache
        if hasattr(self.cache_manager, 'layers'):
            redis_cache = self.cache_manager.layers.get('redis')
            if redis_cache:
                await redis_cache.clear(pattern)
                invalidated_count += 1
        
        self.metrics['pattern_invalidations'] += invalidated_count
        self.metrics['total_invalidations'] += 1
        
        logger.info(f"Pattern invalidation '{pattern}': {invalidated_count} entries")
    
    async def _invalidate_tag(self, tag: str):
        """Invalidate all cache entries with a specific tag."""
        # Application cache layer
        if hasattr(self.cache_manager, 'layers'):
            app_cache = self.cache_manager.layers.get('application')
            if app_cache and hasattr(app_cache, 'invalidate_tag'):
                count = app_cache.invalidate_tag(tag)
                self.metrics['tag_invalidations'] += count
        
        self.metrics['total_invalidations'] += 1
    
    async def _invalidate_tags(self, tags: List[str]):
        """Invalidate multiple tags."""
        for tag in tags:
            await self._invalidate_tag(tag)
    
    def _glob_to_regex(self, pattern: str) -> re.Pattern:
        """Convert glob pattern to regex."""
        # Escape special regex characters
        pattern = pattern.replace('.', r'\.')
        pattern = pattern.replace('+', r'\+')
        pattern = pattern.replace('?', '.')
        pattern = pattern.replace('*', '.*')
        pattern = pattern.replace('[', r'\[')
        pattern = pattern.replace(']', r'\]')
        
        return re.compile(f"^{pattern}$")
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """Register handler for invalidation events."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for event: {event_type}")
    
    async def handle_event(self, event: InvalidationEvent):
        """Handle invalidation event."""
        # Apply matching rules
        for rule in self.rules:
            if self._rule_matches(rule, event):
                await self._apply_rule(rule, event)
        
        # Call registered handlers
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
        
        self.metrics['event_invalidations'] += 1
    
    def _rule_matches(self, rule: InvalidationRule, event: InvalidationEvent) -> bool:
        """Check if rule matches event."""
        # Check conditions
        for key, value in rule.conditions.items():
            event_value = event.data.get(key)
            if event_value != value:
                return False
        
        return True
    
    async def _apply_rule(self, rule: InvalidationRule, event: InvalidationEvent):
        """Apply invalidation rule."""
        if rule.strategy == InvalidationStrategy.IMMEDIATE:
            await self.invalidate(
                keys=[rule.target],
                strategy=InvalidationStrategy.IMMEDIATE
            )
        elif rule.strategy == InvalidationStrategy.CASCADE:
            await self.invalidate(
                keys=[rule.target],
                strategy=InvalidationStrategy.CASCADE
            )
        elif rule.strategy == InvalidationStrategy.PATTERN:
            await self._invalidate_pattern(rule.target)
        elif rule.strategy == InvalidationStrategy.TAG:
            await self._invalidate_tag(rule.target)
    
    async def _batch_processor(self):
        """Process invalidation queue in batches."""
        batch = []
        batch_timeout = 0.1  # 100ms
        last_process_time = time.time()
        
        while True:
            try:
                # Try to get item with timeout
                try:
                    item = await asyncio.wait_for(
                        self.invalidation_queue.get(),
                        timeout=batch_timeout
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass
                
                # Process batch if it's full or timeout reached
                should_process = (
                    len(batch) >= 100 or
                    (batch and time.time() - last_process_time >= batch_timeout)
                )
                
                if should_process and batch:
                    await self._process_batch(batch)
                    batch = []
                    last_process_time = time.time()
                    
            except asyncio.CancelledError:
                # Process remaining items
                if batch:
                    await self._process_batch(batch)
                break
            except Exception as e:
                logger.error(f"Batch processor error: {e}")
    
    async def _process_batch(self, batch: List[InvalidationEvent]):
        """Process a batch of invalidation events."""
        # Group by invalidation type
        keys_to_invalidate = set()
        tags_to_invalidate = set()
        patterns_to_invalidate = set()
        
        for event in batch:
            keys_to_invalidate.update(event.affected_keys)
            tags_to_invalidate.update(event.affected_tags)
            if 'pattern' in event.data:
                patterns_to_invalidate.add(event.data['pattern'])
        
        # Perform batch invalidations
        if keys_to_invalidate:
            await self.cache_manager.delete(list(keys_to_invalidate))
        
        for tag in tags_to_invalidate:
            await self._invalidate_tag(tag)
        
        for pattern in patterns_to_invalidate:
            if pattern:
                await self._invalidate_pattern(pattern)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get invalidation metrics."""
        return {
            **self.metrics,
            'scheduled_tasks': len(self.scheduled_tasks),
            'rules_count': len(self.rules),
            'dependencies_count': len(self.dependencies),
            'queue_size': self.invalidation_queue.qsize()
        }


# Pre-configured invalidation strategies
class SmartInvalidator(CacheInvalidator):
    """
    Smart invalidator with ML-based prediction of invalidation patterns.
    """
    
    def __init__(self, cache_manager: Any):
        super().__init__(cache_manager)
        self.access_patterns: Dict[str, List[float]] = {}
        self.invalidation_history: List[Dict[str, Any]] = []
        self.prediction_model = None
    
    def track_access(self, key: str):
        """Track cache key access for pattern learning."""
        if key not in self.access_patterns:
            self.access_patterns[key] = []
        
        self.access_patterns[key].append(time.time())
        
        # Keep only recent accesses
        cutoff = time.time() - 3600  # 1 hour
        self.access_patterns[key] = [
            t for t in self.access_patterns[key] if t > cutoff
        ]
    
    def predict_invalidation_time(self, key: str) -> Optional[float]:
        """Predict when a cache key should be invalidated."""
        if key not in self.access_patterns:
            return None
        
        accesses = self.access_patterns[key]
        if len(accesses) < 2:
            return None
        
        # Simple prediction: average time between accesses
        intervals = [
            accesses[i+1] - accesses[i]
            for i in range(len(accesses)-1)
        ]
        
        avg_interval = sum(intervals) / len(intervals)
        last_access = accesses[-1]
        
        # Predict next invalidation
        return last_access + avg_interval * 1.5
    
    async def auto_invalidate(self):
        """Automatically invalidate based on predictions."""
        current_time = time.time()
        
        for key, predicted_time in self.get_predictions().items():
            if predicted_time <= current_time:
                await self.invalidate(keys=[key])
                logger.info(f"Auto-invalidated key: {key}")
    
    def get_predictions(self) -> Dict[str, float]:
        """Get all invalidation predictions."""
        predictions = {}
        
        for key in self.access_patterns:
            predicted_time = self.predict_invalidation_time(key)
            if predicted_time:
                predictions[key] = predicted_time
        
        return predictions


# Common invalidation patterns
def create_time_based_rules() -> List[InvalidationRule]:
    """Create time-based invalidation rules."""
    return [
        InvalidationRule(
            strategy=InvalidationStrategy.PATTERN,
            target="session:*",
            scheduled_time=datetime.now() + timedelta(hours=1),
            metadata={"description": "Hourly session cleanup"}
        ),
        InvalidationRule(
            strategy=InvalidationStrategy.TAG,
            target="temporary",
            scheduled_time=datetime.now() + timedelta(minutes=15),
            metadata={"description": "Clean temporary data"}
        )
    ]


def create_event_based_rules() -> List[InvalidationRule]:
    """Create event-based invalidation rules."""
    return [
        InvalidationRule(
            strategy=InvalidationStrategy.CASCADE,
            target="user:*",
            conditions={"event_type": "user_update"},
            cascade_targets=["profile:*", "preferences:*"],
            metadata={"description": "Invalidate user data on update"}
        ),
        InvalidationRule(
            strategy=InvalidationStrategy.PATTERN,
            target="api:v1:*",
            conditions={"event_type": "api_deployment"},
            metadata={"description": "Clear API cache on deployment"}
        )
    ]