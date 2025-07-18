"""Integration models."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class IntegrationType(str, Enum):
    """Types of integrations."""
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    WORDPRESS = "wordpress"
    GITHUB = "github"


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"


class OAuthToken(BaseModel):
    """OAuth token storage."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    encrypted: bool = True
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookConfig(BaseModel):
    """Webhook configuration."""
    endpoint_url: str
    events: List[str]
    secret: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered_at: Optional[datetime] = None


class IntegrationConfig(BaseModel):
    """Integration specific configuration."""
    api_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    sync_settings: Dict[str, Any] = Field(default_factory=dict)
    field_mappings: Dict[str, str] = Field(default_factory=dict)


class Integration(BaseModel):
    """Integration model."""
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    organization_id: str
    integration_type: IntegrationType
    name: str
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    
    # Authentication
    oauth_token: Optional[OAuthToken] = None
    api_key: Optional[str] = None
    
    # Configuration
    config: IntegrationConfig = Field(default_factory=IntegrationConfig)
    webhook_config: Optional[WebhookConfig] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Statistics
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }