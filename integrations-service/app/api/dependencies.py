"""API dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
import httpx
import logging

from app.core.config import get_settings
from app.core.database import database
from app.services.integration_service import IntegrationService
from app.services.sync_service import SyncService
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
settings = get_settings()

# Security
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current user from auth service."""
    token = credentials.credentials
    
    try:
        # Verify token with auth service
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.auth_service_url}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Auth service request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


# Service dependencies
def get_integration_service() -> IntegrationService:
    """Get integration service instance."""
    return IntegrationService(database)


def get_sync_service() -> SyncService:
    """Get sync service instance."""
    return SyncService(database)


def get_webhook_service() -> WebhookService:
    """Get webhook service instance."""
    return WebhookService(database)