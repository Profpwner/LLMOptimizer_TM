"""Integration API schemas."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.models import IntegrationType, IntegrationStatus, IntegrationConfig, SyncDirection, SyncStatus


class IntegrationCreate(BaseModel):
    """Schema for creating an integration."""
    integration_type: IntegrationType
    name: str
    config: Optional[IntegrationConfig] = None


class IntegrationUpdate(BaseModel):
    """Schema for updating an integration."""
    name: Optional[str] = None
    config: Optional[IntegrationConfig] = None


class IntegrationResponse(BaseModel):
    """Integration response schema."""
    id: str
    user_id: str
    organization_id: str
    integration_type: IntegrationType
    name: str
    status: IntegrationStatus
    config: IntegrationConfig
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime] = None
    error_message: Optional[str] = None
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    
    class Config:
        orm_mode = True


class IntegrationListResponse(BaseModel):
    """List of integrations response."""
    items: List[IntegrationResponse]
    total: int
    skip: int
    limit: int


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    code: str
    state: str


class OAuthInitResponse(BaseModel):
    """OAuth initialization response."""
    authorization_url: str
    state: str


class ConnectionTestResponse(BaseModel):
    """Connection test response."""
    is_connected: bool
    message: str
    tested_at: datetime


class SyncRequest(BaseModel):
    """Sync request schema."""
    entity_types: List[str]
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    filters: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class SyncResponse(BaseModel):
    """Sync response schema."""
    sync_job_id: str
    status: SyncStatus
    created_at: datetime
    message: str