"""Multi-Factor Authentication models."""

from enum import Enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class MFAMethod(str, Enum):
    """Supported MFA methods."""
    TOTP = "totp"  # Time-based One-Time Password
    SMS = "sms"    # SMS verification
    EMAIL = "email"  # Email verification
    BACKUP_CODES = "backup_codes"  # Backup codes
    WEBAUTHN = "webauthn"  # WebAuthn/FIDO2
    PUSH = "push"  # Push notifications


class MFASetup(BaseModel):
    """MFA setup configuration for users."""
    
    __tablename__ = 'mfa_setups'
    
    # User reference
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # MFA method
    method = Column(String(20), nullable=False)
    
    # Method-specific data
    secret = Column(String(255), nullable=True)  # Encrypted TOTP secret
    phone_number = Column(String(50), nullable=True)  # For SMS
    email = Column(String(255), nullable=True)  # For email MFA
    device_name = Column(String(255), nullable=True)  # For TOTP/WebAuthn
    
    # WebAuthn specific
    credential_id = Column(String(255), nullable=True)
    public_key = Column(String(1000), nullable=True)
    
    # Status
    is_primary = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Verification
    verification_code = Column(String(10), nullable=True)
    verification_attempts = Column(Integer, default=0, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Usage tracking
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    use_count = Column(Integer, default=0, nullable=False)
    
    # Backup codes reference
    backup_codes_generated = Column(Boolean, default=False, nullable=False)
    backup_codes_generated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="mfa_setups")
    backup_codes = relationship("MFABackupCode", back_populates="mfa_setup", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'method', 'device_name', name='uq_user_mfa_device'),
        Index('idx_mfa_user_method', 'user_id', 'method'),
        Index('idx_mfa_user_active', 'user_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<MFASetup(id={self.id}, user_id={self.user_id}, method={self.method})>"


class MFABackupCode(BaseModel):
    """Backup codes for MFA recovery."""
    
    __tablename__ = 'mfa_backup_codes'
    
    # References
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    mfa_setup_id = Column(UUID(as_uuid=True), ForeignKey('mfa_setups.id'), nullable=False)
    
    # Code
    code_hash = Column(String(255), nullable=False, unique=True)
    
    # Usage
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    used_ip = Column(String(45), nullable=True)
    used_user_agent = Column(String(500), nullable=True)
    
    # Relationships
    mfa_setup = relationship("MFASetup", back_populates="backup_codes")
    
    __table_args__ = (
        Index('idx_backup_code_user', 'user_id'),
        Index('idx_backup_code_hash', 'code_hash'),
    )
    
    def __repr__(self):
        return f"<MFABackupCode(id={self.id}, user_id={self.user_id}, is_used={self.is_used})>"