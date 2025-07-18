"""PostgreSQL models for multi-tenant LLMOptimizer platform."""

from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, JSON,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    Table, Enum as SQLEnum, ARRAY, Numeric
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import UUID as SQLUUID

from .base import Base, BaseModel, TenantModel


class PlanType(str, Enum):
    """Subscription plan types."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class UserRole(str, Enum):
    """User roles within an organization."""
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"


class ContentStatus(str, Enum):
    """Content optimization status."""
    DRAFT = "draft"
    PROCESSING = "processing"
    OPTIMIZED = "optimized"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Association tables for many-to-many relationships
user_organizations = Table(
    'user_organizations',
    Base.metadata,
    Column('user_id', SQLUUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('organization_id', SQLUUID(as_uuid=True), ForeignKey('organizations.id'), primary_key=True),
    Column('role', SQLEnum(UserRole), nullable=False, default=UserRole.VIEWER),
    Column('joined_at', Base.metadata.info.get('timestamp_type'), server_default=Base.metadata.info.get('func_now')),
    Column('is_primary', Boolean, default=False)
)


class Organization(BaseModel):
    """Organization model for multi-tenancy."""
    
    __tablename__ = 'organizations'
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Subscription details
    plan_type = Column(SQLEnum(PlanType), nullable=False, default=PlanType.FREE)
    plan_details = Column(JSON, nullable=True, default={})
    subscription_expires_at = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    
    # Quotas and limits
    max_users = Column(Integer, default=5)
    max_content_items = Column(Integer, default=100)
    max_api_calls_per_month = Column(Integer, default=10000)
    storage_quota_gb = Column(Float, default=10.0)
    
    # Settings
    settings = Column(JSON, nullable=True, default={})
    features = Column(ARRAY(String), default=[])
    
    # Billing
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    billing_email = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    users = relationship("User", secondary=user_organizations, back_populates="organizations")
    api_keys = relationship("APIKey", back_populates="organization", cascade="all, delete-orphan")
    content_items = relationship("Content", back_populates="organization", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint('max_users > 0', name='check_max_users_positive'),
        CheckConstraint('max_content_items > 0', name='check_max_content_items_positive'),
        CheckConstraint('storage_quota_gb > 0', name='check_storage_quota_positive'),
        Index('idx_org_plan_active', 'plan_type', 'is_active'),
    )


class User(BaseModel):
    """User model with multi-organization support."""
    
    __tablename__ = 'users'
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(255), nullable=True)
    
    # Profile
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, nullable=True, default={})
    
    # Security
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(255), nullable=True)
    last_login_at = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # Support IPv6
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    
    # System
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    organizations = relationship("Organization", secondary=user_organizations, back_populates="users")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
    )


class APIKey(TenantModel):
    """API Key model for programmatic access."""
    
    __tablename__ = 'api_keys'
    
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(10), nullable=False)  # First few chars for identification
    
    # Permissions
    scopes = Column(ARRAY(String), default=[], nullable=False)
    rate_limit_per_hour = Column(Integer, default=1000)
    
    # Usage tracking
    last_used_at = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Expiration
    expires_at = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    
    __table_args__ = (
        Index('idx_apikey_org_active', 'org_id', 'is_active'),
        Index('idx_apikey_prefix', 'key_prefix'),
    )


class Content(TenantModel):
    """Content model for optimization tracking."""
    
    __tablename__ = 'content'
    
    title = Column(String(500), nullable=False)
    slug = Column(String(500), nullable=False)
    content_type = Column(String(50), nullable=False)  # article, product, landing_page, etc.
    
    # Status and scoring
    status = Column(SQLEnum(ContentStatus), nullable=False, default=ContentStatus.DRAFT)
    optimization_score = Column(Numeric(5, 2), nullable=True)
    readability_score = Column(Numeric(5, 2), nullable=True)
    seo_score = Column(Numeric(5, 2), nullable=True)
    
    # Metadata
    word_count = Column(Integer, nullable=True)
    language = Column(String(10), default='en', nullable=False)
    target_keywords = Column(ARRAY(String), default=[], nullable=False)
    
    # Version control
    version = Column(Integer, default=1, nullable=False)
    published_version = Column(Integer, nullable=True)
    
    # Analytics
    view_count = Column(Integer, default=0)
    click_through_rate = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    
    # Storage reference (MongoDB)
    mongodb_id = Column(String(24), nullable=True, unique=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="content_items")
    optimizations = relationship("ContentOptimization", back_populates="content", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('org_id', 'slug', 'version', name='uq_org_content_slug_version'),
        Index('idx_content_org_status', 'org_id', 'status'),
        Index('idx_content_org_type', 'org_id', 'content_type'),
        Index('idx_content_scores', 'optimization_score', 'seo_score'),
    )


class ContentOptimization(TenantModel):
    """Track content optimization history and suggestions."""
    
    __tablename__ = 'content_optimizations'
    
    content_id = Column(SQLUUID(as_uuid=True), ForeignKey('content.id'), nullable=False)
    optimization_type = Column(String(50), nullable=False)  # seo, readability, ai_rewrite, etc.
    
    # Scores
    before_score = Column(Numeric(5, 2), nullable=True)
    after_score = Column(Numeric(5, 2), nullable=True)
    improvement_percentage = Column(Float, nullable=True)
    
    # Details
    suggestions = Column(JSON, nullable=True, default=[])
    applied_changes = Column(JSON, nullable=True, default=[])
    
    # AI Model used
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    
    # Cost tracking
    api_cost = Column(Numeric(10, 4), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    
    # Relationships
    content = relationship("Content", back_populates="optimizations")
    
    __table_args__ = (
        Index('idx_optimization_content_type', 'content_id', 'optimization_type'),
        Index('idx_optimization_org_date', 'org_id', 'created_at'),
    )


class UserSession(BaseModel):
    """User session tracking for security and analytics."""
    
    __tablename__ = 'user_sessions'
    
    user_id = Column(SQLUUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    
    # Session details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_type = Column(String(50), nullable=True)
    
    # Expiration
    expires_at = Column(Base.metadata.info.get('timestamp_type'), nullable=False)
    last_activity = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    
    # Security
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(Base.metadata.info.get('timestamp_type'), nullable=True)
    revoke_reason = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'is_active'),
        Index('idx_session_expires', 'expires_at'),
    )