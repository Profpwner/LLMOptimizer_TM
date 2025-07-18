"""
Request batching for optimized API throughput.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Generic
from dataclasses import dataclass, field
import uuid
from collections import defaultdict
import logging
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class BatchingStrategy(Enum):
    """Batching strategies."""
    TIME_BASED = "time"  # Batch by time window
    SIZE_BASED = "size"  # Batch by number of items
    ADAPTIVE = "adaptive"  # Adaptive batching based on load


@dataclass
class BatchRequest(Generic[T]):
    """Individual request in a batch."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: T = None
    timestamp: float = field(default_factory=time.time)
    future: asyncio.Future = field(default_factory=asyncio.Future)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    max_batch_size: int = 100
    max_wait_time: float = 0.1  # seconds
    min_batch_size: int = 1
    strategy: BatchingStrategy = BatchingStrategy.ADAPTIVE
    parallel_batches: int = 4
    retry_failed_items: bool = True
    max_retries: int = 3


class BatchProcessor(Generic[T, R]):
    """
    High-performance request batching for API optimization.
    Supports 100K+ concurrent requests.
    """
    
    def __init__(
        self,
        batch_handler: Callable[[List[T]], List[R]],
        config: Optional[BatchConfig] = None
    ):
        self.batch_handler = batch_handler
        self.config = config or BatchConfig()
        
        # Request queues
        self.pending_requests: List[BatchRequest[T]] = []
        self.request_lock = asyncio.Lock()
        
        # Batch processing
        self.processing = False
        self.batch_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.metrics = {
            'total_requests': 0,
            'total_batches': 0,
            'average_batch_size': 0,
            'average_wait_time': 0,
            'failed_requests': 0,
            'retry_count': 0
        }
        
        # Adaptive batching parameters
        self.adaptive_params = {
            'current_batch_size': self.config.max_batch_size,
            'current_wait_time': self.config.max_wait_time,
            'throughput_history': [],
            'latency_history': []
        }
    
    async def start(self):
        """Start the batch processor."""
        if self.processing:
            return
        
        self.processing = True
        self.batch_task = asyncio.create_task(self._batch_processor())
        logger.info("BatchProcessor started")
    
    async def stop(self):
        """Stop the batch processor."""
        self.processing = False
        
        if self.batch_task:
            self.batch_task.cancel()
            try:
                await self.batch_task
            except asyncio.CancelledError:
                pass
        
        # Process remaining requests
        if self.pending_requests:
            await self._process_batch(self.pending_requests)
            self.pending_requests.clear()
        
        logger.info("BatchProcessor stopped")
    
    async def submit(self, data: T, metadata: Optional[Dict[str, Any]] = None) -> R:
        """Submit a request for batch processing."""
        request = BatchRequest(data=data, metadata=metadata or {})
        
        async with self.request_lock:
            self.pending_requests.append(request)
            self.metrics['total_requests'] += 1
        
        # Wait for result
        try:
            result = await request.future
            return result
        except Exception as e:
            self.metrics['failed_requests'] += 1
            raise
    
    async def submit_many(self, items: List[T]) -> List[R]:
        """Submit multiple items for batch processing."""
        futures = []
        
        for item in items:
            request = BatchRequest(data=item)
            async with self.request_lock:
                self.pending_requests.append(request)
            futures.append(request.future)
        
        self.metrics['total_requests'] += len(items)
        
        # Wait for all results
        results = await asyncio.gather(*futures, return_exceptions=True)
        
        # Count failures
        failures = sum(1 for r in results if isinstance(r, Exception))
        self.metrics['failed_requests'] += failures
        
        return results
    
    async def _batch_processor(self):
        """Main batch processing loop."""
        while self.processing:
            try:
                # Get batch parameters based on strategy
                batch_size, wait_time = self._get_batch_parameters()
                
                # Wait for batch to fill or timeout
                start_time = time.time()
                
                while True:
                    async with self.request_lock:
                        ready = (
                            len(self.pending_requests) >= batch_size or
                            (time.time() - start_time) >= wait_time
                        )
                        
                        if ready and self.pending_requests:
                            # Extract batch
                            batch = self.pending_requests[:batch_size]
                            self.pending_requests = self.pending_requests[batch_size:]
                            break
                    
                    if not self.pending_requests:
                        await asyncio.sleep(0.01)
                        start_time = time.time()
                        continue
                    
                    await asyncio.sleep(0.001)
                
                # Process batch
                await self._process_batch(batch)
                
                # Update metrics
                self._update_metrics(batch, time.time() - start_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processor error: {e}")
                await asyncio.sleep(0.1)
    
    def _get_batch_parameters(self) -> Tuple[int, float]:
        """Get batch size and wait time based on strategy."""
        if self.config.strategy == BatchingStrategy.TIME_BASED:
            return self.config.max_batch_size, self.config.max_wait_time
        
        elif self.config.strategy == BatchingStrategy.SIZE_BASED:
            return self.config.max_batch_size, float('inf')
        
        elif self.config.strategy == BatchingStrategy.ADAPTIVE:
            return self._adaptive_parameters()
        
        return self.config.max_batch_size, self.config.max_wait_time
    
    def _adaptive_parameters(self) -> Tuple[int, float]:
        """Calculate adaptive batching parameters based on load."""
        # Simple adaptive algorithm
        if not self.adaptive_params['throughput_history']:
            return (
                self.adaptive_params['current_batch_size'],
                self.adaptive_params['current_wait_time']
            )
        
        # Calculate average throughput and latency
        avg_throughput = sum(self.adaptive_params['throughput_history'][-10:]) / min(10, len(self.adaptive_params['throughput_history']))
        avg_latency = sum(self.adaptive_params['latency_history'][-10:]) / min(10, len(self.adaptive_params['latency_history']))
        
        # Adjust parameters
        if avg_latency > 0.5:  # High latency
            # Reduce batch size
            self.adaptive_params['current_batch_size'] = max(
                self.config.min_batch_size,
                int(self.adaptive_params['current_batch_size'] * 0.8)
            )
        elif avg_throughput < 100:  # Low throughput
            # Increase batch size
            self.adaptive_params['current_batch_size'] = min(
                self.config.max_batch_size,
                int(self.adaptive_params['current_batch_size'] * 1.2)
            )
        
        return (
            self.adaptive_params['current_batch_size'],
            self.adaptive_params['current_wait_time']
        )
    
    async def _process_batch(self, batch: List[BatchRequest[T]]):
        """Process a batch of requests."""
        if not batch:
            return
        
        batch_data = [req.data for req in batch]
        
        try:
            # Process batch with parallel execution if configured
            if self.config.parallel_batches > 1 and len(batch_data) > self.config.parallel_batches:
                results = await self._process_parallel_batches(batch_data)
            else:
                results = await self._execute_batch_handler(batch_data)
            
            # Verify results count
            if len(results) != len(batch):
                raise ValueError(f"Batch handler returned {len(results)} results for {len(batch)} requests")
            
            # Set results
            for request, result in zip(batch, results):
                if isinstance(result, Exception):
                    request.future.set_exception(result)
                else:
                    request.future.set_result(result)
            
            self.metrics['total_batches'] += 1
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            
            # Handle failures
            if self.config.retry_failed_items:
                await self._retry_failed_batch(batch, e)
            else:
                # Set exception for all requests
                for request in batch:
                    request.future.set_exception(e)
    
    async def _execute_batch_handler(self, batch_data: List[T]) -> List[R]:
        """Execute the batch handler function."""
        if asyncio.iscoroutinefunction(self.batch_handler):
            return await self.batch_handler(batch_data)
        else:
            # Run in executor for sync handlers
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.batch_handler, batch_data)
    
    async def _process_parallel_batches(self, batch_data: List[T]) -> List[R]:
        """Process large batch in parallel sub-batches."""
        chunk_size = len(batch_data) // self.config.parallel_batches
        chunks = [
            batch_data[i:i + chunk_size]
            for i in range(0, len(batch_data), chunk_size)
        ]
        
        # Process chunks in parallel
        results = await asyncio.gather(*[
            self._execute_batch_handler(chunk)
            for chunk in chunks
        ])
        
        # Flatten results
        return [item for sublist in results for item in sublist]
    
    async def _retry_failed_batch(self, batch: List[BatchRequest[T]], error: Exception):
        """Retry failed batch requests."""
        for request in batch:
            retry_count = request.metadata.get('retry_count', 0)
            
            if retry_count < self.config.max_retries:
                # Re-queue for retry
                request.metadata['retry_count'] = retry_count + 1
                request.metadata['last_error'] = str(error)
                
                async with self.request_lock:
                    self.pending_requests.append(request)
                
                self.metrics['retry_count'] += 1
            else:
                # Max retries exceeded
                request.future.set_exception(error)
    
    def _update_metrics(self, batch: List[BatchRequest], wait_time: float):
        """Update processing metrics."""
        batch_size = len(batch)
        
        # Update average batch size
        total_batches = self.metrics['total_batches']
        if total_batches > 0:
            current_avg = self.metrics['average_batch_size']
            self.metrics['average_batch_size'] = (
                (current_avg * (total_batches - 1) + batch_size) / total_batches
            )
        else:
            self.metrics['average_batch_size'] = batch_size
        
        # Update average wait time
        avg_request_wait = sum(
            time.time() - req.timestamp for req in batch
        ) / batch_size
        
        if total_batches > 0:
            current_avg = self.metrics['average_wait_time']
            self.metrics['average_wait_time'] = (
                (current_avg * (total_batches - 1) + avg_request_wait) / total_batches
            )
        else:
            self.metrics['average_wait_time'] = avg_request_wait
        
        # Update adaptive parameters
        if self.config.strategy == BatchingStrategy.ADAPTIVE:
            throughput = batch_size / wait_time if wait_time > 0 else 0
            self.adaptive_params['throughput_history'].append(throughput)
            self.adaptive_params['latency_history'].append(avg_request_wait)
            
            # Keep history limited
            if len(self.adaptive_params['throughput_history']) > 100:
                self.adaptive_params['throughput_history'].pop(0)
                self.adaptive_params['latency_history'].pop(0)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            **self.metrics,
            'pending_requests': len(self.pending_requests),
            'adaptive_params': self.adaptive_params if self.config.strategy == BatchingStrategy.ADAPTIVE else None
        }


class TypedBatchProcessor:
    """
    Batch processor for multiple request types.
    """
    
    def __init__(self):
        self.processors: Dict[str, BatchProcessor] = {}
        
    def register_handler(
        self,
        request_type: str,
        handler: Callable,
        config: Optional[BatchConfig] = None
    ):
        """Register a batch handler for a specific request type."""
        self.processors[request_type] = BatchProcessor(handler, config)
    
    async def start_all(self):
        """Start all batch processors."""
        for processor in self.processors.values():
            await processor.start()
    
    async def stop_all(self):
        """Stop all batch processors."""
        for processor in self.processors.values():
            await processor.stop()
    
    async def submit(self, request_type: str, data: Any) -> Any:
        """Submit a request of a specific type."""
        if request_type not in self.processors:
            raise ValueError(f"Unknown request type: {request_type}")
        
        return await self.processors[request_type].submit(data)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all processors."""
        return {
            req_type: processor.get_metrics()
            for req_type, processor in self.processors.items()
        }


# Example batch handlers
async def database_batch_handler(queries: List[Tuple[str, tuple]]) -> List[Any]:
    """Example: Batch database queries."""
    # This would connect to actual database
    results = []
    for query, params in queries:
        # Simulate query execution
        results.append({"query": query, "result": "mock_result"})
    return results


async def api_batch_handler(requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Example: Batch API requests."""
    # This would make actual HTTP requests
    results = []
    for request in requests:
        # Simulate API call
        results.append({"status": 200, "data": request})
    return results