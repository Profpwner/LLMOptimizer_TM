"""Integration management API endpoints."""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import secrets

from app.models import Integration, IntegrationType, IntegrationStatus
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationListResponse,
    OAuthCallbackRequest,
    OAuthInitResponse,
    ConnectionTestResponse,
    SyncRequest,
    SyncResponse,
)
from app.services.integration_service import IntegrationService
from app.services.sync_service import SyncService
from app.core.database import database
from app.integrations.registry import IntegrationRegistry
from app.api.dependencies import get_current_user, get_integration_service, get_sync_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=IntegrationListResponse)
async def list_integrations(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    integration_type: Optional[IntegrationType] = None,
    status: Optional[IntegrationStatus] = None,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """List user's integrations."""
    filters = {
        "user_id": current_user["id"],
        "organization_id": current_user.get("organization_id"),
    }
    
    if integration_type:
        filters["integration_type"] = integration_type
    if status:
        filters["status"] = status
    
    integrations = await service.list_integrations(filters, skip, limit)
    total = await service.count_integrations(filters)
    
    return IntegrationListResponse(
        items=integrations,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    integration: IntegrationCreate,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Create a new integration."""
    # Check if integration type is supported
    if not IntegrationRegistry.get(integration.integration_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integration type {integration.integration_type} is not supported"
        )
    
    # Create integration
    new_integration = Integration(
        user_id=current_user["id"],
        organization_id=current_user.get("organization_id"),
        integration_type=integration.integration_type,
        name=integration.name,
        config=integration.config,
    )
    
    created = await service.create_integration(new_integration)
    return IntegrationResponse.from_orm(created)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: str,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Get integration details."""
    integration = await service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this integration"
        )
    
    return IntegrationResponse.from_orm(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    update: IntegrationUpdate,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Update integration configuration."""
    integration = await service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this integration"
        )
    
    updated = await service.update_integration(integration_id, update)
    return IntegrationResponse.from_orm(updated)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Delete an integration."""
    integration = await service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this integration"
        )
    
    await service.delete_integration(integration_id)


# OAuth endpoints
@router.get("/{integration_id}/oauth/init", response_model=OAuthInitResponse)
async def init_oauth(
    integration_id: str,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Initialize OAuth flow for an integration."""
    integration = await service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this integration"
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store state in cache for verification
    await service.store_oauth_state(state, integration_id, current_user["id"])
    
    # Get authorization URL
    auth_url = await service.get_oauth_authorization_url(integration, state)
    
    return OAuthInitResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get("/{integration_type}/callback")
async def oauth_callback(
    integration_type: IntegrationType,
    code: str = Query(...),
    state: str = Query(...),
    service: IntegrationService = Depends(get_integration_service),
):
    """Handle OAuth callback."""
    # Verify state
    oauth_data = await service.verify_oauth_state(state)
    if not oauth_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state"
        )
    
    integration_id = oauth_data["integration_id"]
    user_id = oauth_data["user_id"]
    
    # Get integration
    integration = await service.get_integration(integration_id)
    if not integration or integration.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Exchange code for token
    try:
        await service.complete_oauth_flow(integration, code)
        return {"status": "success", "message": "OAuth connection established"}
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {str(e)}"
        )


# Connection management
@router.post("/{integration_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    integration_id: str,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Test integration connection."""
    integration = await service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to test this integration"
        )
    
    # Test connection
    is_connected, message = await service.test_integration_connection(integration)
    
    return ConnectionTestResponse(
        is_connected=is_connected,
        message=message,
        tested_at=datetime.utcnow(),
    )


@router.post("/{integration_id}/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    integration_id: str,
    current_user=Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
):
    """Disconnect an integration (remove auth tokens)."""
    integration = await service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to disconnect this integration"
        )
    
    await service.disconnect_integration(integration_id)


# Sync operations
@router.post("/{integration_id}/sync", response_model=SyncResponse)
async def trigger_sync(
    integration_id: str,
    sync_request: SyncRequest,
    current_user=Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service),
    sync_service: SyncService = Depends(get_sync_service),
):
    """Trigger a manual sync for an integration."""
    integration = await integration_service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to sync this integration"
        )
    
    # Check if connected
    if integration.status != IntegrationStatus.CONNECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not connected"
        )
    
    # Create sync job
    sync_job = await sync_service.create_sync_job(
        integration=integration,
        entity_types=sync_request.entity_types,
        direction=sync_request.direction,
        filters=sync_request.filters,
        options=sync_request.options,
    )
    
    # Trigger sync asynchronously
    await sync_service.queue_sync_job(sync_job)
    
    return SyncResponse(
        sync_job_id=sync_job.id,
        status=sync_job.status,
        created_at=sync_job.created_at,
        message="Sync job created and queued for processing",
    )


@router.get("/{integration_id}/sync/history")
async def get_sync_history(
    integration_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service),
    sync_service: SyncService = Depends(get_sync_service),
):
    """Get sync history for an integration."""
    integration = await integration_service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view sync history"
        )
    
    # Get sync history
    sync_jobs = await sync_service.get_sync_history(integration_id, skip, limit)
    total = await sync_service.count_sync_jobs(integration_id)
    
    return {
        "items": sync_jobs,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{integration_id}/sync/{sync_job_id}")
async def get_sync_job_details(
    integration_id: str,
    sync_job_id: str,
    current_user=Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service),
    sync_service: SyncService = Depends(get_sync_service),
):
    """Get detailed information about a sync job."""
    integration = await integration_service.get_integration(integration_id)
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    # Check ownership
    if integration.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view sync details"
        )
    
    # Get sync job
    sync_job = await sync_service.get_sync_job(sync_job_id)
    
    if not sync_job or sync_job.integration_id != integration_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync job not found"
        )
    
    # Get sync logs
    logs = await sync_service.get_sync_logs(sync_job_id)
    
    return {
        "job": sync_job,
        "logs": logs,
    }