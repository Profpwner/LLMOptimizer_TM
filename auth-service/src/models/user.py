"""User model with enhanced security features."""

from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text, JSON,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Table, Enum as SQLEnum, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, Base


class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class UserRole(str, Enum):
    """System-wide user roles."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    DEVELOPER = "developer"
    USER = "user"


# Association table for user roles
user_roles = Table(
    'user_role_associations',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), server_default='now()', nullable=False),
    Column('assigned_by', UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
)


class User(BaseModel):
    """Enhanced user model with security features."""
    
    __tablename__ = 'users'
    
    # Basic information
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    password_history = Column(ARRAY(String), default=[], nullable=False)
    
    # Email verification
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(255), nullable=True)
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Phone verification
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    phone_verification_code = Column(String(10), nullable=True)
    phone_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Profile
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    timezone = Column(String(50), default='UTC', nullable=False)
    locale = Column(String(10), default='en', nullable=False)
    preferences = Column(JSON, nullable=True, default={})
    
    # Status
    status = Column(SQLEnum(UserStatus), nullable=False, default=UserStatus.PENDING_VERIFICATION)
    status_changed_at = Column(DateTime(timezone=True), nullable=True)
    status_reason = Column(Text, nullable=True)
    
    # Security
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    last_login_location = Column(JSON, nullable=True)  # {country, city, lat, lng}
    last_login_device = Column(JSON, nullable=True)  # {type, browser, os}
    
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    lock_reason = Column(String(255), nullable=True)
    
    # Multi-Factor Authentication
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_methods = Column(ARRAY(String), default=[], nullable=False)
    
    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_sent_at = Column(DateTime(timezone=True), nullable=True)
    password_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # Compliance
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    terms_version = Column(String(50), nullable=True)
    privacy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_version = Column(String(50), nullable=True)
    
    # System
    is_system_user = Column(Boolean, default=False, nullable=False)
    user_metadata = Column(JSON, nullable=True, default={})
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    oauth_connections = relationship("OAuthConnection", back_populates="user", cascade="all, delete-orphan")
    mfa_setups = relationship("MFASetup", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")
    security_events = relationship("SecurityEvent", back_populates="user", cascade="all, delete-orphan")
    device_fingerprints = relationship("DeviceFingerprint", back_populates="user", cascade="all, delete-orphan")
    roles = relationship(
        "Role", 
        secondary="user_role_associations", 
        back_populates="users",
        primaryjoin="User.id==user_role_associations.c.user_id",
        secondaryjoin="user_role_associations.c.role_id==Role.id"
    )
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        CheckConstraint('failed_login_attempts >= 0', name='check_failed_login_attempts_positive'),
        Index('idx_user_email_status', 'email', 'status'),
        Index('idx_user_username_status', 'username', 'status'),
        Index('idx_user_phone', 'phone_number'),
        Index('idx_user_last_login', 'last_login_at'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
    
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.status == UserStatus.LOCKED:
            return True
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def can_login(self) -> bool:
        """Check if user can login."""
        return (
            self.status == UserStatus.ACTIVE and
            not self.is_locked() and
            self.is_email_verified
        )