"""Role-Based Access Control models."""

from enum import Enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text, Integer,
    ForeignKey, UniqueConstraint, Index, Table
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from .base import BaseModel, Base


class ResourceType(str, Enum):
    """Types of resources that can be protected."""
    API = "api"
    CONTENT = "content"
    ORGANIZATION = "organization"
    USER = "user"
    REPORT = "report"
    SETTINGS = "settings"
    BILLING = "billing"
    ADMIN = "admin"


class PermissionAction(str, Enum):
    """Standard CRUD actions plus custom actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXPORT = "export"
    IMPORT = "import"
    EXECUTE = "execute"
    APPROVE = "approve"
    PUBLISH = "publish"


# Association table for role permissions
role_permissions = Table(
    'role_permission_associations',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id'), primary_key=True),
    Column('granted_at', DateTime(timezone=True), server_default='now()', nullable=False),
    Column('granted_by', UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
)


class Role(BaseModel):
    """Role definition for RBAC."""
    
    __tablename__ = 'roles'
    
    # Role information
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Role hierarchy
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True)
    level = Column(Integer, default=0, nullable=False)  # 0 = top level
    
    # Role type
    is_system_role = Column(Boolean, default=False, nullable=False)
    is_custom_role = Column(Boolean, default=False, nullable=False)
    
    # Organization scope (null = global role)
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    role_metadata = Column(JSON, nullable=True, default={})
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship(
        "User", 
        secondary="user_role_associations", 
        back_populates="roles",
        primaryjoin="Role.id==user_role_associations.c.role_id",
        secondaryjoin="user_role_associations.c.user_id==User.id"
    )
    parent_role = relationship("Role", remote_side="Role.id", backref="child_roles")
    
    __table_args__ = (
        UniqueConstraint('name', 'org_id', name='uq_role_name_org'),
        Index('idx_role_name', 'name'),
        Index('idx_role_org', 'org_id'),
        Index('idx_role_parent', 'parent_role_id'),
    )
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"
    
    def get_all_permissions(self):
        """Get all permissions including inherited from parent roles."""
        permissions = set(self.permissions)
        if self.parent_role:
            permissions.update(self.parent_role.get_all_permissions())
        return list(permissions)


class Permission(BaseModel):
    """Permission definition."""
    
    __tablename__ = 'permissions'
    
    # Permission information
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Resource and action
    resource_type = Column(String(50), nullable=False)
    actions = Column(ARRAY(String), nullable=False, default=[])
    
    # Scope
    scope = Column(String(50), nullable=True)  # e.g., 'own', 'org', 'global'
    conditions = Column(JSON, nullable=True)  # Additional conditions
    
    # Permission category
    category = Column(String(50), nullable=True)  # For grouping in UI
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_system_permission = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    role_metadata = Column(JSON, nullable=True, default={})
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    __table_args__ = (
        Index('idx_permission_resource', 'resource_type'),
        Index('idx_permission_category', 'category'),
    )
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name})>"
    
    def allows_action(self, action: str) -> bool:
        """Check if permission allows specific action."""
        return action in self.actions or "*" in self.actions


class RolePermission(BaseModel):
    """Additional attributes for role-permission relationship."""
    
    __tablename__ = 'role_permission_attributes'
    
    # References
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey('permissions.id'), nullable=False)
    
    # Additional constraints
    resource_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # Specific resource IDs
    excluded_actions = Column(ARRAY(String), nullable=True)  # Actions to exclude
    
    # Time-based access
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Conditions
    conditions = Column(JSON, nullable=True)  # e.g., {"ip_range": "10.0.0.0/8"}
    
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
        Index('idx_role_permission', 'role_id', 'permission_id'),
    )
    
    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"
    
    def is_valid(self) -> bool:
        """Check if permission is currently valid."""
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True