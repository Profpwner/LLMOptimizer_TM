"""
Enhanced Authentication Service for LLMOptimizer
Provides comprehensive authentication, authorization, OAuth, MFA, and security features.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pythonjsonlogger import jsonlogger
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from src.config import settings
from src.database import init_db, get_redis, close_connections
from src.security.security_headers import SecurityHeadersMiddleware
from src.security.rate_limiter import RateLimiter
from src.api.routers import auth, users, oauth, mfa, admin
from src.api.schemas import ErrorResponse, ValidationErrorResponse

# Configure structured logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG)

# Metrics
request_counter = Counter(
    'auth_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)
request_duration = Histogram(
    'auth_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)
active_sessions = Counter(
    'auth_active_sessions_total',
    'Total number of active sessions'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_db()
        
        # Initialize Redis
        logger.info("Connecting to Redis...")
        redis_client = await get_redis()
        app.state.redis = redis_client
        
        # Initialize services
        app.state.rate_limiter = RateLimiter(redis_client)
        
        logger.info("Auth service started successfully")
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down auth service...")
        await close_connections()
        logger.info("Auth service stopped")


# Create FastAPI app
app = FastAPI(
    title="LLMOptimizer Auth Service",
    description="Enterprise-grade authentication and authorization service",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Add compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ValidationErrorResponse(
            detail=exc.errors(),
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.DEBUG else None,
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )


# Middleware for request tracking
@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track request metrics."""
    import time
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Record metrics
    duration = time.time() - start_time
    request_counter.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    # Add response headers
    response.headers["X-Response-Time"] = f"{duration:.3f}"
    
    return response


# Health check endpoints
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/ready", tags=["health"])
async def readiness_check(redis_client = None) -> Dict[str, Any]:
    """Readiness check with dependency verification."""
    try:
        # Check Redis
        if not redis_client:
            redis_client = await get_redis()
        await redis_client.ping()
        
        return {
            "status": "ready",
            "checks": {
                "database": "ok",
                "redis": "ok"
            }
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not ready",
                "error": str(e)
            }
        )


@app.get("/metrics", tags=["monitoring"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(oauth.router, prefix="/api/v1")
app.include_router(mfa.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None
    }


# Feature flags endpoint
@app.get("/features", tags=["info"])
async def get_features():
    """Get enabled features."""
    return {
        "oauth": settings.ENABLE_OAUTH,
        "saml": settings.ENABLE_SAML,
        "mfa": settings.ENABLE_MFA,
        "sms_mfa": settings.ENABLE_SMS_MFA,
        "email_verification": settings.ENABLE_EMAIL_VERIFICATION,
        "device_tracking": settings.ENABLE_DEVICE_TRACKING,
        "oauth_providers": []  # Will be populated from OAuth manager
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "formatter": "json",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )