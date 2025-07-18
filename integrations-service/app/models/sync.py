"""Sync job and log models."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class SyncStatus(str, Enum):
    """Sync job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncDirection(str, Enum):
    """Sync direction."""
    INBOUND = "inbound"  # From integration to our system
    OUTBOUND = "outbound"  # From our system to integration
    BIDIRECTIONAL = "bidirectional"


class SyncJob(BaseModel):
    """Sync job model."""
    id: Optional[str] = Field(default=None, alias="_id")
    integration_id: str
    user_id: str
    organization_id: str
    
    # Job details
    status: SyncStatus = SyncStatus.PENDING
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    entity_types: List[str]  # e.g., ["contacts", "companies", "deals"]
    
    # Timing
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Progress
    total_records: int = 0
    processed_records: int = 0
    created_records: int = 0
    updated_records: int = 0
    skipped_records: int = 0
    error_records: int = 0
    
    # Configuration
    filters: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)
    
    # Error handling
    error_message: Optional[str] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SyncLog(BaseModel):
    """Sync operation log."""
    id: Optional[str] = Field(default=None, alias="_id")
    sync_job_id: str
    integration_id: str
    
    # Log details
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str  # INFO, WARNING, ERROR
    operation: str  # e.g., "create_contact", "update_deal"
    entity_type: str
    entity_id: Optional[str] = None
    
    # Operation details
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    
    # Performance
    duration_ms: Optional[int] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }