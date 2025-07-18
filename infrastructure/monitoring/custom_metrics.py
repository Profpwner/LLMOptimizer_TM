"""
Custom metrics collection for LLMOptimizer.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, Gauge, Summary
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Central metrics collector for LLMOptimizer application.
    """
    
    def __init__(self):
        # HTTP Metrics
        self.http_requests = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status', 'service']
        )
        
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint', 'service'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
        )
        
        self.http_request_size = Summary(
            'http_request_size_bytes',
            'HTTP request size',
            ['method', 'endpoint', 'service']
        )
        
        self.http_response_size = Summary(
            'http_response_size_bytes',
            'HTTP response size',
            ['method', 'endpoint', 'service']
        )
        
        # LLM Metrics
        self.llm_requests = Counter(
            'llm_api_requests_total',
            'Total LLM API requests',
            ['provider', 'model', 'operation']
        )
        
        self.llm_errors = Counter(
            'llm_api_errors_total',
            'Total LLM API errors',
            ['provider', 'model', 'error_type']
        )
        
        self.llm_tokens = Counter(
            'llm_tokens_used_total',
            'Total tokens used',
            ['provider', 'model', 'type']  # type: prompt/completion
        )
        
        self.llm_response_time = Histogram(
            'llm_response_duration_seconds',
            'LLM API response time',
            ['provider', 'model'],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60)
        )
        
        self.llm_cost = Counter(
            'llm_api_cost_dollars',
            'LLM API cost in dollars',
            ['provider', 'model']
        )
        
        # Business Metrics
        self.brand_visibility = Gauge(
            'brand_visibility_score',
            'Current brand visibility score',
            ['brand', 'platform']
        )
        
        self.content_optimizations = Counter(
            'content_optimizations_total',
            'Total content optimizations',
            ['type', 'status']
        )
        
        self.semantic_queue = Gauge(
            'semantic_analysis_queue_size',
            'Semantic analysis queue size'
        )
        
        self.content_quality_score = Gauge(
            'content_quality_score',
            'Content quality score',
            ['content_type', 'category']
        )
        
        # Cache Metrics
        self.cache_operations = Counter(
            'cache_operations_total',
            'Total cache operations',
            ['operation', 'cache_type', 'status']
        )
        
        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio',
            ['cache_type']
        )
        
        # Database Metrics
        self.db_connections = Gauge(
            'db_connections_active',
            'Active database connections',
            ['database', 'pool']
        )
        
        self.db_query_duration = Histogram(
            'db_query_duration_seconds',
            'Database query duration',
            ['database', 'operation', 'table'],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5)
        )
        
        # Authentication Metrics
        self.auth_users = Gauge(
            'auth_active_users_total',
            'Total active users',
            ['auth_type']
        )
        
        self.auth_attempts = Counter(
            'auth_login_attempts_total',
            'Total login attempts',
            ['method', 'status']
        )
        
        self.auth_token_operations = Counter(
            'auth_token_operations_total',
            'Token operations',
            ['operation', 'token_type']
        )
        
        # Performance Metrics
        self.task_processing_time = Histogram(
            'task_processing_duration_seconds',
            'Task processing duration',
            ['task_type', 'status'],
            buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 300)
        )
        
        self.queue_size = Gauge(
            'task_queue_size',
            'Task queue size',
            ['queue_name']
        )
        
        # Custom application metrics
        self.semantic_similarity_computation = Histogram(
            'semantic_similarity_computation_seconds',
            'Time to compute semantic similarity',
            ['algorithm'],
            buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5)
        )
        
        self.content_mesh_generation = Histogram(
            'content_mesh_generation_seconds',
            'Time to generate content mesh',
            ['size_category'],  # small, medium, large
            buckets=(0.1, 0.5, 1, 5, 10, 30, 60)
        )
    
    def track_http_request(self, method: str, endpoint: str, status: int, 
                          service: str, duration: float, request_size: int = 0, 
                          response_size: int = 0):
        """Track HTTP request metrics."""
        self.http_requests.labels(
            method=method,
            endpoint=endpoint,
            status=str(status),
            service=service
        ).inc()
        
        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint,
            service=service
        ).observe(duration)
        
        if request_size > 0:
            self.http_request_size.labels(
                method=method,
                endpoint=endpoint,
                service=service
            ).observe(request_size)
        
        if response_size > 0:
            self.http_response_size.labels(
                method=method,
                endpoint=endpoint,
                service=service
            ).observe(response_size)
    
    def track_llm_request(self, provider: str, model: str, operation: str,
                         tokens_prompt: int, tokens_completion: int,
                         duration: float, cost: float = 0, error: str = None):
        """Track LLM API request metrics."""
        self.llm_requests.labels(
            provider=provider,
            model=model,
            operation=operation
        ).inc()
        
        if error:
            self.llm_errors.labels(
                provider=provider,
                model=model,
                error_type=error
            ).inc()
        
        self.llm_tokens.labels(
            provider=provider,
            model=model,
            type='prompt'
        ).inc(tokens_prompt)
        
        self.llm_tokens.labels(
            provider=provider,
            model=model,
            type='completion'
        ).inc(tokens_completion)
        
        self.llm_response_time.labels(
            provider=provider,
            model=model
        ).observe(duration)
        
        if cost > 0:
            self.llm_cost.labels(
                provider=provider,
                model=model
            ).inc(cost)
    
    def update_brand_visibility(self, brand: str, platform: str, score: float):
        """Update brand visibility score."""
        self.brand_visibility.labels(
            brand=brand,
            platform=platform
        ).set(score)
    
    def track_content_optimization(self, optimization_type: str, status: str):
        """Track content optimization."""
        self.content_optimizations.labels(
            type=optimization_type,
            status=status
        ).inc()
    
    def track_cache_operation(self, operation: str, cache_type: str, 
                            hit: bool = None):
        """Track cache operation."""
        status = 'hit' if hit else 'miss' if hit is not None else 'unknown'
        self.cache_operations.labels(
            operation=operation,
            cache_type=cache_type,
            status=status
        ).inc()
    
    def update_cache_hit_ratio(self, cache_type: str, ratio: float):
        """Update cache hit ratio."""
        self.cache_hit_ratio.labels(cache_type=cache_type).set(ratio)
    
    def track_db_query(self, database: str, operation: str, table: str, 
                      duration: float):
        """Track database query."""
        self.db_query_duration.labels(
            database=database,
            operation=operation,
            table=table
        ).observe(duration)
    
    def update_db_connections(self, database: str, pool: str, count: int):
        """Update database connection count."""
        self.db_connections.labels(
            database=database,
            pool=pool
        ).set(count)
    
    def track_auth_attempt(self, method: str, success: bool):
        """Track authentication attempt."""
        status = 'success' if success else 'failed'
        self.auth_attempts.labels(
            method=method,
            status=status
        ).inc()
    
    def update_active_users(self, auth_type: str, count: int):
        """Update active users count."""
        self.auth_users.labels(auth_type=auth_type).set(count)
    
    def track_task_processing(self, task_type: str, status: str, duration: float):
        """Track task processing."""
        self.task_processing_time.labels(
            task_type=task_type,
            status=status
        ).observe(duration)
    
    def update_queue_size(self, queue_name: str, size: int):
        """Update queue size."""
        self.queue_size.labels(queue_name=queue_name).set(size)


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Decorators for automatic metric collection
def track_http_endpoint(service: str):
    """Decorator to track HTTP endpoint metrics."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(request, *args, **kwargs):
            start_time = time.time()
            status = 500
            try:
                response = await func(request, *args, **kwargs)
                status = response.status
                return response
            finally:
                duration = time.time() - start_time
                metrics_collector.track_http_request(
                    method=request.method,
                    endpoint=request.path,
                    status=status,
                    service=service,
                    duration=duration,
                    request_size=request.content_length or 0
                )
        
        @wraps(func)
        def sync_wrapper(request, *args, **kwargs):
            start_time = time.time()
            status = 500
            try:
                response = func(request, *args, **kwargs)
                status = response.status_code
                return response
            finally:
                duration = time.time() - start_time
                metrics_collector.track_http_request(
                    method=request.method,
                    endpoint=request.path,
                    status=status,
                    service=service,
                    duration=duration
                )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def track_llm_call(provider: str, model: str, operation: str):
    """Decorator to track LLM API calls."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            tokens_prompt = 0
            tokens_completion = 0
            cost = 0
            
            try:
                result = await func(*args, **kwargs)
                # Extract token counts from result if available
                if isinstance(result, dict):
                    tokens_prompt = result.get('usage', {}).get('prompt_tokens', 0)
                    tokens_completion = result.get('usage', {}).get('completion_tokens', 0)
                    cost = result.get('cost', 0)
                return result
            except Exception as e:
                error = type(e).__name__
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.track_llm_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    duration=duration,
                    cost=cost,
                    error=error
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            tokens_prompt = 0
            tokens_completion = 0
            cost = 0
            
            try:
                result = func(*args, **kwargs)
                # Extract token counts from result if available
                if isinstance(result, dict):
                    tokens_prompt = result.get('usage', {}).get('prompt_tokens', 0)
                    tokens_completion = result.get('usage', {}).get('completion_tokens', 0)
                    cost = result.get('cost', 0)
                return result
            except Exception as e:
                error = type(e).__name__
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.track_llm_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    duration=duration,
                    cost=cost,
                    error=error
                )
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


@asynccontextmanager
async def track_db_operation(database: str, operation: str, table: str):
    """Context manager to track database operations."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics_collector.track_db_query(
            database=database,
            operation=operation,
            table=table,
            duration=duration
        )


class MetricsMiddleware:
    """Middleware for automatic metrics collection."""
    
    def __init__(self, app, service_name: str):
        self.app = app
        self.service_name = service_name
    
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            start_time = time.time()
            status = 500
            
            async def send_wrapper(message):
                nonlocal status
                if message['type'] == 'http.response.start':
                    status = message['status']
                await send(message)
            
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                duration = time.time() - start_time
                metrics_collector.track_http_request(
                    method=scope['method'],
                    endpoint=scope['path'],
                    status=status,
                    service=self.service_name,
                    duration=duration
                )
        else:
            await self.app(scope, receive, send)