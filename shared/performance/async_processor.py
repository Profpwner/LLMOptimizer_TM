"""
Async processing optimization for handling high-concurrency workloads.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from functools import wraps
import pickle
import uuid

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Priority(Enum):
    """Task priority levels."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class AsyncTask:
    """Represents an async task with metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    func: Callable = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    created_at: float = field(default_factory=time.time)
    timeout: Optional[float] = None
    retries: int = 0
    max_retries: int = 3
    result: Any = None
    error: Optional[Exception] = None
    completed: bool = False


class AsyncProcessor:
    """
    High-performance async processing engine for 100K+ concurrent operations.
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        max_queue_size: int = 10000,
        enable_cpu_bound_executor: bool = True
    ):
        self.max_workers = max_workers or min(32, (multiprocessing.cpu_count() or 1) + 4)
        self.max_queue_size = max_queue_size
        
        # Task queues by priority
        self.task_queues: Dict[Priority, asyncio.Queue] = {
            priority: asyncio.Queue(maxsize=max_queue_size)
            for priority in Priority
        }
        
        # Worker pool
        self.workers: List[asyncio.Task] = []
        self.running = False
        
        # Task tracking
        self.active_tasks: Dict[str, AsyncTask] = {}
        self.completed_tasks: Dict[str, AsyncTask] = {}
        
        # Executors for CPU-bound tasks
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_executor = None
        if enable_cpu_bound_executor:
            self.process_executor = None  # Lazy initialization
        
        # Metrics
        self.metrics = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_retried': 0,
            'avg_execution_time': 0,
            'queue_sizes': {}
        }
        
        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(self.max_workers * 2)
    
    async def start(self):
        """Start the async processor."""
        if self.running:
            return
        
        self.running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        # Start metrics collector
        asyncio.create_task(self._metrics_collector())
        
        logger.info(f"AsyncProcessor started with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the async processor gracefully."""
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to complete
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        # Shutdown executors
        self.thread_executor.shutdown(wait=True)
        if self.process_executor:
            self.process_executor.shutdown(wait=True)
        
        logger.info("AsyncProcessor stopped")
    
    async def submit(
        self,
        func: Callable,
        *args,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None,
        **kwargs
    ) -> str:
        """Submit a task for async execution."""
        task = AsyncTask(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout
        )
        
        # Add to appropriate queue
        await self.task_queues[priority].put(task)
        self.active_tasks[task.id] = task
        self.metrics['tasks_submitted'] += 1
        
        return task.id
    
    async def submit_batch(
        self,
        tasks: List[Tuple[Callable, tuple, dict]],
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> List[str]:
        """Submit multiple tasks as a batch."""
        task_ids = []
        
        for func, args, kwargs in tasks:
            task_id = await self.submit(
                func, *args,
                priority=priority,
                timeout=timeout,
                **kwargs
            )
            task_ids.append(task_id)
        
        return task_ids
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Wait for a task to complete and return its result."""
        start_time = time.time()
        
        while True:
            # Check if task is completed
            if task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
                if task.error:
                    raise task.error
                return task.result
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Task {task_id} timed out")
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
    
    async def wait_for_batch(
        self,
        task_ids: List[str],
        timeout: Optional[float] = None
    ) -> List[Any]:
        """Wait for multiple tasks to complete."""
        tasks = [
            self.wait_for_task(task_id, timeout)
            for task_id in task_ids
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def map_async(
        self,
        func: Callable,
        iterable: List[Any],
        priority: Priority = Priority.NORMAL,
        chunk_size: int = 1
    ) -> List[str]:
        """Map a function over an iterable asynchronously."""
        task_ids = []
        
        # Process in chunks for better performance
        for i in range(0, len(iterable), chunk_size):
            chunk = iterable[i:i + chunk_size]
            
            async def process_chunk(items):
                return [func(item) for item in items]
            
            task_id = asyncio.create_task(
                self.submit(process_chunk, chunk, priority=priority)
            )
            task_ids.append(task_id)
        
        return task_ids
    
    async def _worker(self, worker_id: str):
        """Worker coroutine that processes tasks from queues."""
        logger.info(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Get task from highest priority queue with available items
                task = None
                for priority in Priority:
                    if not self.task_queues[priority].empty():
                        task = await self.task_queues[priority].get()
                        break
                
                if not task:
                    # No tasks available, wait a bit
                    await asyncio.sleep(0.01)
                    continue
                
                # Process task with semaphore for concurrency control
                async with self.semaphore:
                    await self._process_task(task)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_task(self, task: AsyncTask):
        """Process a single task."""
        start_time = time.time()
        
        try:
            # Determine if task is CPU-bound
            if asyncio.iscoroutinefunction(task.func):
                # Async function
                if task.timeout:
                    result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs),
                        timeout=task.timeout
                    )
                else:
                    result = await task.func(*task.args, **task.kwargs)
            else:
                # Sync function - run in executor
                loop = asyncio.get_event_loop()
                if task.timeout:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.thread_executor,
                            task.func,
                            *task.args
                        ),
                        timeout=task.timeout
                    )
                else:
                    result = await loop.run_in_executor(
                        self.thread_executor,
                        task.func,
                        *task.args
                    )
            
            task.result = result
            task.completed = True
            self.metrics['tasks_completed'] += 1
            
        except asyncio.TimeoutError:
            task.error = asyncio.TimeoutError(f"Task timed out after {task.timeout}s")
            await self._handle_task_failure(task)
            
        except Exception as e:
            task.error = e
            await self._handle_task_failure(task)
        
        finally:
            # Update metrics
            execution_time = time.time() - start_time
            self._update_execution_time(execution_time)
            
            # Move to completed tasks
            self.completed_tasks[task.id] = task
            del self.active_tasks[task.id]
    
    async def _handle_task_failure(self, task: AsyncTask):
        """Handle task failure with retry logic."""
        if task.retries < task.max_retries:
            task.retries += 1
            self.metrics['tasks_retried'] += 1
            
            # Exponential backoff
            await asyncio.sleep(2 ** task.retries)
            
            # Re-queue task with lower priority
            new_priority = Priority(min(task.priority.value + 1, Priority.LOW.value))
            await self.task_queues[new_priority].put(task)
            
            logger.warning(f"Task {task.id} failed, retrying ({task.retries}/{task.max_retries})")
        else:
            task.completed = True
            self.metrics['tasks_failed'] += 1
            logger.error(f"Task {task.id} failed after {task.max_retries} retries: {task.error}")
    
    def _update_execution_time(self, execution_time: float):
        """Update average execution time metric."""
        completed = self.metrics['tasks_completed']
        if completed > 0:
            current_avg = self.metrics['avg_execution_time']
            self.metrics['avg_execution_time'] = (
                (current_avg * (completed - 1) + execution_time) / completed
            )
    
    async def _metrics_collector(self):
        """Collect queue size metrics periodically."""
        while self.running:
            for priority in Priority:
                self.metrics['queue_sizes'][priority.name] = self.task_queues[priority].qsize()
            
            await asyncio.sleep(5)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            **self.metrics,
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'thread_executor_active': self.thread_executor._threads.__len__()
        }
    
    async def run_in_process(self, func: Callable, *args, **kwargs) -> Any:
        """Run CPU-intensive function in separate process."""
        if not self.process_executor:
            self.process_executor = ProcessPoolExecutor(max_workers=self.max_workers // 2)
        
        loop = asyncio.get_event_loop()
        
        # Pickle function and arguments for process execution
        pickled_func = pickle.dumps((func, args, kwargs))
        
        result = await loop.run_in_executor(
            self.process_executor,
            _execute_pickled_function,
            pickled_func
        )
        
        return result


def _execute_pickled_function(pickled_data: bytes) -> Any:
    """Execute pickled function in process pool."""
    func, args, kwargs = pickle.loads(pickled_data)
    return func(*args, **kwargs)


class RateLimitedProcessor(AsyncProcessor):
    """Async processor with rate limiting capabilities."""
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        max_queue_size: int = 10000,
        rate_limit: int = 1000,  # requests per second
        **kwargs
    ):
        super().__init__(max_workers, max_queue_size, **kwargs)
        self.rate_limit = rate_limit
        self.rate_limiter = asyncio.Semaphore(rate_limit)
        self.rate_reset_task = None
    
    async def start(self):
        """Start processor with rate limiting."""
        await super().start()
        self.rate_reset_task = asyncio.create_task(self._reset_rate_limiter())
    
    async def stop(self):
        """Stop processor and rate limiter."""
        if self.rate_reset_task:
            self.rate_reset_task.cancel()
        await super().stop()
    
    async def _reset_rate_limiter(self):
        """Reset rate limiter every second."""
        while self.running:
            await asyncio.sleep(1)
            # Reset semaphore
            self.rate_limiter = asyncio.Semaphore(self.rate_limit)
    
    async def _process_task(self, task: AsyncTask):
        """Process task with rate limiting."""
        async with self.rate_limiter:
            await super()._process_task(task)


# Decorator for async caching
def async_cached(ttl: int = 300):
    """Cache async function results."""
    cache = {}
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            if key in cache:
                result, timestamp = cache[key]
                if time.time() - timestamp < ttl:
                    return result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            cache[key] = (result, time.time())
            
            return result
        
        return wrapper
    
    return decorator