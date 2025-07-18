"""OAuth connection models for social login integration."""

from enum import Enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GITHUB = "github"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    APPLE = "apple"
    CUSTOM = "custom"


class OAuthConnection(BaseModel):
    """OAuth connection for social login."""
    
    __tablename__ = 'oauth_connections'
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Provider information
    provider = Column(String(50), nullable=False)
    provider_user_id = Column(String(255), nullable=False)
    
    # OAuth tokens
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted
    token_type = Column(String(50), default='Bearer', nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Provider profile data
    email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    given_name = Column(String(255), nullable=True)
    family_name = Column(String(255), nullable=True)
    picture_url = Column(String(500), nullable=True)
    locale = Column(String(10), nullable=True)
    
    # Additional provider data
    provider_data = Column(JSON, nullable=True, default={})
    scopes = Column(JSON, nullable=True, default=[])
    
    # Connection status
    is_primary = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    connected_at = Column(DateTime(timezone=True), server_default='now()', nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="oauth_connections")
    
    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user'),
        UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
        Index('idx_oauth_user_provider', 'user_id', 'provider'),
        Index('idx_oauth_provider_id', 'provider', 'provider_user_id'),
    )
    
    def __repr__(self):
        return f"<OAuthConnection(id={self.id}, provider={self.provider}, user_id={self.user_id})>"
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired."""
        if not self.expires_at:
            return False
        return self.expires_at <= datetime.utcnow()
    
    def needs_refresh(self) -> bool:
        """Check if token needs refresh."""
        if not self.refresh_token or not self.expires_at:
            return False
        # Refresh if less than 5 minutes remaining
        time_until_expiry = (self.expires_at - datetime.utcnow()).total_seconds()
        return time_until_expiry < 300  # 5 minutes