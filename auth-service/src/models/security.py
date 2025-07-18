"""Security models for tracking login attempts and security events."""

from enum import Enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text, Integer,
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class LoginAttemptStatus(str, Enum):
    """Login attempt status."""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    SUSPICIOUS = "suspicious"


class SecurityEventType(str, Enum):
    """Types of security events."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    MFA_METHOD_ADDED = "mfa_method_added"
    MFA_METHOD_REMOVED = "mfa_method_removed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SESSION_HIJACK_ATTEMPT = "session_hijack_attempt"
    OAUTH_CONNECTED = "oauth_connected"
    OAUTH_DISCONNECTED = "oauth_disconnected"
    EMAIL_CHANGED = "email_changed"
    PROFILE_UPDATED = "profile_updated"
    PERMISSION_CHANGED = "permission_changed"


class LoginAttempt(BaseModel):
    """Track login attempts for security monitoring."""
    
    __tablename__ = 'login_attempts'
    
    # User reference (nullable for failed attempts with unknown user)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Attempt details
    email = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False)
    failure_reason = Column(String(255), nullable=True)
    
    # Client information
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500), nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Location
    location = Column(JSON, nullable=True)  # {country, city, region, lat, lng}
    is_known_location = Column(Boolean, default=False, nullable=False)
    
    # Security checks
    is_suspicious = Column(Boolean, default=False, nullable=False)
    risk_score = Column(Integer, default=0, nullable=False)
    risk_factors = Column(JSON, nullable=True, default=[])
    
    # Authentication method
    auth_method = Column(String(50), nullable=True)  # password, oauth, saml
    oauth_provider = Column(String(50), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="login_attempts")
    
    __table_args__ = (
        Index('idx_login_attempt_email', 'email'),
        Index('idx_login_attempt_ip', 'ip_address'),
        Index('idx_login_attempt_user_time', 'user_id', 'created_at'),
        Index('idx_login_attempt_status', 'status'),
    )
    
    def __repr__(self):
        return f"<LoginAttempt(id={self.id}, email={self.email}, status={self.status})>"


class SecurityEvent(BaseModel):
    """Track security-related events for audit trail."""
    
    __tablename__ = 'security_events'
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    
    # Client information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Session reference
    session_id = Column(UUID(as_uuid=True), ForeignKey('user_sessions.id'), nullable=True)
    
    # Additional data
    event_metadata = Column(JSON, nullable=True, default={})
    
    # Risk assessment
    risk_level = Column(String(20), nullable=True)  # low, medium, high, critical
    requires_action = Column(Boolean, default=False, nullable=False)
    action_taken = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="security_events")
    
    __table_args__ = (
        Index('idx_security_event_user_type', 'user_id', 'event_type'),
        Index('idx_security_event_time', 'created_at'),
        Index('idx_security_event_risk', 'risk_level', 'requires_action'),
    )
    
    def __repr__(self):
        return f"<SecurityEvent(id={self.id}, user_id={self.user_id}, event_type={self.event_type})>"


class DeviceFingerprint(BaseModel):
    """Track device fingerprints for anomaly detection."""
    
    __tablename__ = 'device_fingerprints'
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Fingerprint
    fingerprint = Column(String(255), nullable=False, index=True)
    
    # Device details
    device_type = Column(String(50), nullable=True)
    device_name = Column(String(255), nullable=True)
    browser = Column(String(50), nullable=True)
    browser_version = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    os_version = Column(String(50), nullable=True)
    
    # Hardware info
    screen_resolution = Column(String(20), nullable=True)
    color_depth = Column(Integer, nullable=True)
    timezone = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    
    # Trust status
    is_trusted = Column(Boolean, default=False, nullable=False)
    trust_score = Column(Integer, default=50, nullable=False)
    
    # Usage
    first_seen_at = Column(DateTime(timezone=True), server_default='now()', nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    seen_count = Column(Integer, default=1, nullable=False)
    
    # Location history
    locations = Column(JSON, nullable=True, default=[])
    
    # Relationships
    user = relationship("User", back_populates="device_fingerprints")
    
    __table_args__ = (
        Index('idx_device_user_fingerprint', 'user_id', 'fingerprint'),
        Index('idx_device_fingerprint', 'fingerprint'),
        Index('idx_device_trust', 'is_trusted', 'trust_score'),
    )
    
    def __repr__(self):
        return f"<DeviceFingerprint(id={self.id}, user_id={self.user_id}, fingerprint={self.fingerprint})>"