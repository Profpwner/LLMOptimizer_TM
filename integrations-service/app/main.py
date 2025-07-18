"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.core.database import database
from app.api import health, integrations, webhooks
from app.utils.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting up integrations service...")
    await database.connect()
    
    yield
    
    # Shutdown
    logger.info("Shutting down integrations service...")
    await database.disconnect()


# Create FastAPI app
app = FastAPI(
    title="LLMOptimizer Integrations Service",
    description="Service for managing enterprise integrations",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(
    integrations.router,
    prefix="/api/v1/integrations",
    tags=["integrations"]
)
app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["webhooks"]
)


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info(f"Service: {settings.service_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Port: {settings.port}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )