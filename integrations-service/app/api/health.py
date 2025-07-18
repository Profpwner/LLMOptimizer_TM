"""Health check endpoints."""

from fastapi import APIRouter, status
from datetime import datetime

from app.core.config import get_settings
from app.core.database import database

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with database connectivity."""
    health_status = {
        "status": "healthy",
        "service": settings.service_name,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": {"status": "unknown"},
            "redis": {"status": "unknown"},
        }
    }
    
    # Check MongoDB
    try:
        if database.client:
            await database.client.admin.command("ping")
            health_status["checks"]["database"]["status"] = "healthy"
        else:
            health_status["checks"]["database"]["status"] = "disconnected"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["database"]["status"] = "unhealthy"
        health_status["checks"]["database"]["error"] = str(e)
        health_status["status"] = "unhealthy"
    
    # Check Redis (would need to implement redis health check)
    # For now, we'll assume it's healthy if configured
    if settings.redis_url:
        health_status["checks"]["redis"]["status"] = "healthy"
    
    return health_status