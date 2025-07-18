"""Rate Limiting and DDoS Protection Middleware

Implements comprehensive rate limiting with multiple strategies to protect
against DDoS attacks and API abuse.
"""

import time
import json
import hashlib
import ipaddress
from typing import Dict, Optional, List, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import redis
from redis.lock import Lock
import logging
from collections import defaultdict
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"  # Adjusts based on system load


@dataclass
class RateLimitRule:
    """Rate limit rule definition"""
    name: str
    limit: int  # Number of requests
    window: int  # Time window in seconds
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_limit: Optional[int] = None  # Allow burst traffic
    key_func: Optional[Callable] = None  # Custom key generation
    cost_func: Optional[Callable] = None  # Custom cost calculation
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)


@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    limit: int
    remaining: int
    reset: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds to wait


class RateLimiter:
    """Advanced rate limiter with multiple strategies"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        default_limit: int = 100,
        default_window: int = 60,
        default_strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW,
        enable_distributed: bool = True,
        enable_adaptive: bool = False,
        burst_multiplier: float = 1.5
    ):
        self.redis_client = redis_client
        self.default_limit = default_limit
        self.default_window = default_window
        self.default_strategy = default_strategy
        self.enable_distributed = enable_distributed
        self.enable_adaptive = enable_adaptive
        self.burst_multiplier = burst_multiplier
        self.rules: Dict[str, RateLimitRule] = {}
        
        # Local cache for performance
        self._local_cache: Dict[str, Dict] = defaultdict(dict)
        self._cache_ttl = 1  # seconds
        
        # Metrics for adaptive rate limiting
        self._request_metrics = defaultdict(lambda: {"total": 0, "blocked": 0})
    
    def add_rule(self, rule: RateLimitRule):
        """Add rate limit rule"""
        self.rules[rule.name] = rule
        logger.info(f"Added rate limit rule: {rule.name}")
    
    def check_rate_limit(
        self,
        key: str,
        rule_name: Optional[str] = None,
        cost: int = 1,
        identifier: Optional[str] = None
    ) -> RateLimitResult:
        """Check if request is within rate limit
        
        Args:
            key: Rate limit key (e.g., IP address, user ID)
            rule_name: Name of rule to apply
            cost: Cost of this request (for weighted rate limiting)
            identifier: Additional identifier for logging
            
        Returns:
            RateLimitResult
        """
        # Get rule
        if rule_name and rule_name in self.rules:
            rule = self.rules[rule_name]
        else:
            # Use default rule
            rule = RateLimitRule(
                name="default",
                limit=self.default_limit,
                window=self.default_window,
                strategy=self.default_strategy
            )
        
        # Check whitelist/blacklist
        if self._is_whitelisted(key, rule):
            return RateLimitResult(
                allowed=True,
                limit=rule.limit,
                remaining=rule.limit,
                reset=int(time.time() + rule.window)
            )
        
        if self._is_blacklisted(key, rule):
            return RateLimitResult(
                allowed=False,
                limit=rule.limit,
                remaining=0,
                reset=int(time.time() + rule.window),
                retry_after=rule.window
            )
        
        # Apply custom key function if provided
        if rule.key_func:
            key = rule.key_func(key)
        
        # Apply custom cost function if provided
        if rule.cost_func:
            cost = rule.cost_func(cost)
        
        # Check rate limit based on strategy
        if rule.strategy == RateLimitStrategy.FIXED_WINDOW:
            result = self._check_fixed_window(key, rule, cost)
        elif rule.strategy == RateLimitStrategy.SLIDING_WINDOW:
            result = self._check_sliding_window(key, rule, cost)
        elif rule.strategy == RateLimitStrategy.TOKEN_BUCKET:
            result = self._check_token_bucket(key, rule, cost)
        elif rule.strategy == RateLimitStrategy.LEAKY_BUCKET:
            result = self._check_leaky_bucket(key, rule, cost)
        elif rule.strategy == RateLimitStrategy.ADAPTIVE:
            result = self._check_adaptive(key, rule, cost)
        else:
            raise ValueError(f"Unknown strategy: {rule.strategy}")
        
        # Update metrics
        self._update_metrics(key, result.allowed)
        
        # Log if blocked
        if not result.allowed:
            logger.warning(
                f"Rate limit exceeded: key={key}, rule={rule.name}, "
                f"identifier={identifier}, cost={cost}"
            )
        
        return result
    
    def _check_fixed_window(self, key: str, rule: RateLimitRule, cost: int) -> RateLimitResult:
        """Fixed window rate limiting"""
        window_key = f"ratelimit:{rule.name}:{key}:{int(time.time() // rule.window)}"
        
        # Use pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        pipe.incrby(window_key, cost)
        pipe.expire(window_key, rule.window)
        results = pipe.execute()
        
        current_count = results[0]
        allowed = current_count <= rule.limit
        
        return RateLimitResult(
            allowed=allowed,
            limit=rule.limit,
            remaining=max(0, rule.limit - current_count),
            reset=int((int(time.time() // rule.window) + 1) * rule.window),
            retry_after=rule.window if not allowed else None
        )
    
    def _check_sliding_window(self, key: str, rule: RateLimitRule, cost: int) -> RateLimitResult:
        """Sliding window rate limiting using sorted sets"""
        now = time.time()
        window_key = f"ratelimit:{rule.name}:{key}:sliding"
        window_start = now - rule.window
        
        # Lua script for atomic sliding window check
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])
        local window_start = now - window
        
        -- Remove old entries
        redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
        
        -- Count current requests
        local current = redis.call('ZCARD', key)
        
        -- Check if adding this request would exceed limit
        if current + cost > limit then
            return {0, current, limit}
        end
        
        -- Add new request
        for i = 1, cost do
            redis.call('ZADD', key, now, now .. ':' .. i .. ':' .. math.random())
        end
        
        -- Set expiry
        redis.call('EXPIRE', key, window)
        
        -- Get new count
        local new_count = redis.call('ZCARD', key)
        
        return {1, new_count, limit}
        """
        
        result = self.redis_client.eval(
            lua_script,
            1,
            window_key,
            str(now),
            str(rule.window),
            str(rule.limit),
            str(cost)
        )
        
        allowed = bool(result[0])
        current_count = result[1]
        
        return RateLimitResult(
            allowed=allowed,
            limit=rule.limit,
            remaining=max(0, rule.limit - current_count),
            reset=int(now + rule.window),
            retry_after=rule.window if not allowed else None
        )
    
    def _check_token_bucket(self, key: str, rule: RateLimitRule, cost: int) -> RateLimitResult:
        """Token bucket rate limiting"""
        bucket_key = f"ratelimit:{rule.name}:{key}:bucket"
        now = time.time()
        
        # Calculate refill rate (tokens per second)
        refill_rate = rule.limit / rule.window
        
        # Burst limit
        burst_limit = rule.burst_limit or int(rule.limit * self.burst_multiplier)
        
        # Lua script for atomic token bucket
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local cost = tonumber(ARGV[2])
        local refill_rate = tonumber(ARGV[3])
        local burst_limit = tonumber(ARGV[4])
        local window = tonumber(ARGV[5])
        
        -- Get current bucket state
        local bucket = redis.call('HGETALL', key)
        local tokens = burst_limit
        local last_refill = now
        
        if #bucket > 0 then
            for i = 1, #bucket, 2 do
                if bucket[i] == 'tokens' then
                    tokens = tonumber(bucket[i + 1])
                elseif bucket[i] == 'last_refill' then
                    last_refill = tonumber(bucket[i + 1])
                end
            end
            
            -- Calculate tokens to add
            local elapsed = now - last_refill
            local new_tokens = elapsed * refill_rate
            tokens = math.min(burst_limit, tokens + new_tokens)
        end
        
        -- Check if we have enough tokens
        if tokens < cost then
            -- Update last refill time
            redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, window * 2)
            
            -- Calculate when enough tokens will be available
            local tokens_needed = cost - tokens
            local wait_time = tokens_needed / refill_rate
            
            return {0, tokens, burst_limit, wait_time}
        end
        
        -- Consume tokens
        tokens = tokens - cost
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, window * 2)
        
        return {1, tokens, burst_limit, 0}
        """
        
        result = self.redis_client.eval(
            lua_script,
            1,
            bucket_key,
            str(now),
            str(cost),
            str(refill_rate),
            str(burst_limit),
            str(rule.window)
        )
        
        allowed = bool(result[0])
        remaining_tokens = int(result[1])
        retry_after = int(result[3]) if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            limit=burst_limit,
            remaining=remaining_tokens,
            reset=int(now + rule.window),
            retry_after=retry_after
        )
    
    def _check_leaky_bucket(self, key: str, rule: RateLimitRule, cost: int) -> RateLimitResult:
        """Leaky bucket rate limiting"""
        bucket_key = f"ratelimit:{rule.name}:{key}:leaky"
        now = time.time()
        
        # Leak rate (requests per second)
        leak_rate = rule.limit / rule.window
        
        # Lua script for atomic leaky bucket
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local cost = tonumber(ARGV[2])
        local leak_rate = tonumber(ARGV[3])
        local capacity = tonumber(ARGV[4])
        local window = tonumber(ARGV[5])
        
        -- Get current bucket state
        local bucket = redis.call('HGETALL', key)
        local volume = 0
        local last_leak = now
        
        if #bucket > 0 then
            for i = 1, #bucket, 2 do
                if bucket[i] == 'volume' then
                    volume = tonumber(bucket[i + 1])
                elseif bucket[i] == 'last_leak' then
                    last_leak = tonumber(bucket[i + 1])
                end
            end
            
            -- Calculate leaked amount
            local elapsed = now - last_leak
            local leaked = elapsed * leak_rate
            volume = math.max(0, volume - leaked)
        end
        
        -- Check if bucket would overflow
        if volume + cost > capacity then
            -- Update state
            redis.call('HSET', key, 'volume', volume, 'last_leak', now)
            redis.call('EXPIRE', key, window * 2)
            
            -- Calculate wait time
            local overflow = (volume + cost) - capacity
            local wait_time = overflow / leak_rate
            
            return {0, volume, capacity, wait_time}
        end
        
        -- Add to bucket
        volume = volume + cost
        redis.call('HSET', key, 'volume', volume, 'last_leak', now)
        redis.call('EXPIRE', key, window * 2)
        
        return {1, capacity - volume, capacity, 0}
        """
        
        result = self.redis_client.eval(
            lua_script,
            1,
            bucket_key,
            str(now),
            str(cost),
            str(leak_rate),
            str(rule.limit),
            str(rule.window)
        )
        
        allowed = bool(result[0])
        remaining_capacity = int(result[1])
        retry_after = int(result[3]) if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            limit=rule.limit,
            remaining=remaining_capacity,
            reset=int(now + rule.window),
            retry_after=retry_after
        )
    
    def _check_adaptive(self, key: str, rule: RateLimitRule, cost: int) -> RateLimitResult:
        """Adaptive rate limiting based on system metrics"""
        # Get system load metrics
        load_factor = self._get_system_load_factor()
        
        # Adjust limit based on load
        adjusted_limit = int(rule.limit * (2 - load_factor))  # Reduce limit as load increases
        
        # Create adjusted rule
        adjusted_rule = RateLimitRule(
            name=f"{rule.name}_adaptive",
            limit=adjusted_limit,
            window=rule.window,
            strategy=RateLimitStrategy.SLIDING_WINDOW
        )
        
        # Use sliding window with adjusted limit
        result = self._check_sliding_window(key, adjusted_rule, cost)
        
        # Adjust result to show original limit
        result.limit = rule.limit
        
        return result
    
    def _get_system_load_factor(self) -> float:
        """Get system load factor (0.0 to 1.0)"""
        # This could check CPU, memory, request queue depth, etc.
        # For now, return a simple metric based on recent request rate
        
        total_requests = sum(m["total"] for m in self._request_metrics.values())
        blocked_requests = sum(m["blocked"] for m in self._request_metrics.values())
        
        if total_requests == 0:
            return 0.0
        
        # Higher block rate = higher load
        block_rate = blocked_requests / total_requests
        
        # Smooth the metric
        return min(1.0, block_rate * 2)
    
    def _is_whitelisted(self, key: str, rule: RateLimitRule) -> bool:
        """Check if key is whitelisted"""
        for pattern in rule.whitelist:
            if self._match_pattern(key, pattern):
                return True
        return False
    
    def _is_blacklisted(self, key: str, rule: RateLimitRule) -> bool:
        """Check if key is blacklisted"""
        for pattern in rule.blacklist:
            if self._match_pattern(key, pattern):
                return True
        return False
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Match key against pattern (supports wildcards and CIDR)"""
        # Check for CIDR notation
        if '/' in pattern:
            try:
                network = ipaddress.ip_network(pattern)
                addr = ipaddress.ip_address(key)
                return addr in network
            except ValueError:
                pass
        
        # Check for wildcard
        if '*' in pattern:
            import fnmatch
            return fnmatch.fnmatch(key, pattern)
        
        # Exact match
        return key == pattern
    
    def _update_metrics(self, key: str, allowed: bool):
        """Update request metrics"""
        self._request_metrics[key]["total"] += 1
        if not allowed:
            self._request_metrics[key]["blocked"] += 1
        
        # Clean old metrics periodically
        if len(self._request_metrics) > 10000:
            # Keep only recent entries
            cutoff = time.time() - 300  # 5 minutes
            self._request_metrics = {
                k: v for k, v in self._request_metrics.items()
                if v.get("last_update", 0) > cutoff
            }
    
    def reset_limits(self, key: str, rule_name: Optional[str] = None):
        """Reset rate limits for a key"""
        if rule_name:
            patterns = [
                f"ratelimit:{rule_name}:{key}:*"
            ]
        else:
            patterns = [
                f"ratelimit:*:{key}:*"
            ]
        
        for pattern in patterns:
            for key in self.redis_client.scan_iter(match=pattern):
                self.redis_client.delete(key)
        
        logger.info(f"Reset rate limits for key: {key}")


class RateLimitMiddleware:
    """Rate limiting middleware for web applications"""
    
    def __init__(
        self,
        app=None,
        rate_limiter: Optional[RateLimiter] = None,
        key_func: Optional[Callable] = None,
        error_handler: Optional[Callable] = None,
        header_prefix: str = "X-RateLimit-"
    ):
        self.rate_limiter = rate_limiter
        self.key_func = key_func or self._default_key_func
        self.error_handler = error_handler or self._default_error_handler
        self.header_prefix = header_prefix
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with application"""
        # For FastAPI
        if hasattr(app, 'middleware'):
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.requests import Request
            from starlette.responses import Response
            
            class RateLimitMiddlewareWrapper(BaseHTTPMiddleware):
                def __init__(self, app, rate_limit_middleware):
                    super().__init__(app)
                    self.rate_limit_middleware = rate_limit_middleware
                
                async def dispatch(self, request: Request, call_next):
                    # Get rate limit key
                    key = await self.rate_limit_middleware.key_func(request)
                    
                    # Check rate limit
                    rule_name = self.rate_limit_middleware._get_rule_name(request)
                    result = self.rate_limit_middleware.rate_limiter.check_rate_limit(
                        key,
                        rule_name,
                        identifier=str(request.url)
                    )
                    
                    if not result.allowed:
                        return await self.rate_limit_middleware.error_handler(
                            request, result
                        )
                    
                    # Process request
                    response = await call_next(request)
                    
                    # Add rate limit headers
                    self.rate_limit_middleware._add_headers(response, result)
                    
                    return response
            
            app.add_middleware(RateLimitMiddlewareWrapper, rate_limit_middleware=self)
    
    async def _default_key_func(self, request) -> str:
        """Default key function (uses IP address)"""
        # Get client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host
        
        return ip
    
    async def _default_error_handler(self, request, result: RateLimitResult):
        """Default error handler"""
        from starlette.responses import JSONResponse
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests",
                "retry_after": result.retry_after
            },
            headers={
                "Retry-After": str(result.retry_after) if result.retry_after else "60"
            }
        )
    
    def _get_rule_name(self, request) -> Optional[str]:
        """Get rule name based on request"""
        # Could map endpoints to specific rules
        # For now, return None to use default
        return None
    
    def _add_headers(self, response, result: RateLimitResult):
        """Add rate limit headers to response"""
        response.headers[f"{self.header_prefix}Limit"] = str(result.limit)
        response.headers[f"{self.header_prefix}Remaining"] = str(result.remaining)
        response.headers[f"{self.header_prefix}Reset"] = str(result.reset)
        
        if result.retry_after:
            response.headers["Retry-After"] = str(result.retry_after)


# Decorator for function-level rate limiting
def rate_limit(
    limit: int = 100,
    window: int = 60,
    key_func: Optional[Callable] = None,
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
):
    """Decorator for rate limiting functions"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Implementation for async functions
            # Would need access to rate limiter instance
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Implementation for sync functions
            # Would need access to rate limiter instance
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator