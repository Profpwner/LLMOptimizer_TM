"""User session model for tracking active sessions."""

from enum import Enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Integer,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class SessionStatus(str, Enum):
    """Session status types."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    IDLE = "idle"


class UserSession(BaseModel):
    """User session tracking for security and analytics."""
    
    __tablename__ = 'user_sessions'
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Session tokens
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=False, index=True)
    csrf_token = Column(String(255), nullable=True)
    
    # Session details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Device information
    device_type = Column(String(50), nullable=True)  # desktop, mobile, tablet
    device_name = Column(String(255), nullable=True)
    browser = Column(String(50), nullable=True)
    browser_version = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    os_version = Column(String(50), nullable=True)
    
    # Location information
    location = Column(JSON, nullable=True)  # {country, city, region, lat, lng}
    timezone = Column(String(50), nullable=True)
    
    # Session lifecycle
    status = Column(String(20), nullable=False, default=SessionStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default='now()', nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoke_reason = Column(String(255), nullable=True)
    
    # Security flags
    is_trusted = Column(Boolean, default=False, nullable=False)
    is_suspicious = Column(Boolean, default=False, nullable=False)
    security_flags = Column(JSON, nullable=True, default=[])
    
    # Session metadata
    login_method = Column(String(50), nullable=True)  # password, oauth, saml, mfa
    oauth_provider = Column(String(50), nullable=True)
    mfa_verified = Column(Boolean, default=False, nullable=False)
    
    # Activity tracking
    request_count = Column(Integer, default=0, nullable=False)
    last_request_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'status'),
        Index('idx_session_expires', 'expires_at'),
        Index('idx_session_device_fingerprint', 'device_fingerprint'),
        Index('idx_session_last_activity', 'last_activity'),
        CheckConstraint('request_count >= 0', name='check_request_count_positive'),
    )
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, status={self.status})>"
    
    def is_active(self) -> bool:
        """Check if session is active."""
        return (
            self.status == SessionStatus.ACTIVE and
            self.expires_at > datetime.utcnow() and
            not self.revoked_at
        )
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return self.expires_at <= datetime.utcnow()
    
    def should_refresh(self) -> bool:
        """Check if session tokens should be refreshed."""
        # Refresh if more than half the session lifetime has passed
        if self.created_at and self.expires_at:
            total_lifetime = (self.expires_at - self.created_at).total_seconds()
            elapsed = (datetime.utcnow() - self.created_at).total_seconds()
            return elapsed > (total_lifetime / 2)
        return False