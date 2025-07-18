"""Base PostgreSQL models and utilities for multi-tenant architecture."""

from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, UUID as SQLUUID, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property


Base = declarative_base()


class TenantMixin:
    """Mixin for multi-tenant models with row-level security."""
    
    @declared_attr
    def org_id(cls):
        """Organization ID for tenant isolation."""
        return Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    
    @declared_attr
    def __table_args__(cls):
        """Add RLS policy to tables."""
        return (
            {"info": {"enable_rls": True}},
        )


class TimestampMixin:
    """Mixin for timestamp fields."""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
        )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True)
    
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False)
    
    @hybrid_property
    def is_active(self) -> bool:
        """Check if record is active (not deleted)."""
        return not self.is_deleted and self.deleted_at is None


class AuditMixin:
    """Mixin for audit fields."""
    
    @declared_attr
    def created_by(cls):
        return Column(SQLUUID(as_uuid=True), nullable=True)
    
    @declared_attr
    def updated_by(cls):
        return Column(SQLUUID(as_uuid=True), nullable=True)
    
    @declared_attr
    def version(cls):
        return Column(String(50), nullable=True)
    
    @declared_attr
    def metadata_json(cls):
        return Column(JSON, nullable=True, default={})


class BaseModel(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Base model with common fields."""
    
    __abstract__ = True
    
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model from dictionary."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ["id", "created_at"]:
                setattr(self, key, value)


class TenantModel(BaseModel, TenantMixin):
    """Base model for tenant-specific data."""
    
    __abstract__ = True