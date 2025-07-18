"""Role-Based Access Control (RBAC) Implementation

This module implements fine-grained RBAC with hierarchical roles, permissions,
and resource-based access control following the principle of least privilege.
"""

import enum
from typing import Dict, List, Set, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
import redis
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Permission(enum.Enum):
    """System permissions enumeration"""
    # User Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"
    
    # Content Management
    CONTENT_CREATE = "content:create"
    CONTENT_READ = "content:read"
    CONTENT_UPDATE = "content:update"
    CONTENT_DELETE = "content:delete"
    CONTENT_PUBLISH = "content:publish"
    CONTENT_ANALYZE = "content:analyze"
    
    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    ANALYTICS_CONFIGURE = "analytics:configure"
    
    # Integration Management
    INTEGRATION_CREATE = "integration:create"
    INTEGRATION_READ = "integration:read"
    INTEGRATION_UPDATE = "integration:update"
    INTEGRATION_DELETE = "integration:delete"
    INTEGRATION_EXECUTE = "integration:execute"
    
    # ML Model Management
    MODEL_TRAIN = "model:train"
    MODEL_DEPLOY = "model:deploy"
    MODEL_READ = "model:read"
    MODEL_UPDATE = "model:update"
    MODEL_DELETE = "model:delete"
    
    # System Administration
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_AUDIT = "system:audit"
    SYSTEM_BACKUP = "system:backup"
    
    # API Management
    API_KEY_CREATE = "api:key:create"
    API_KEY_READ = "api:key:read"
    API_KEY_REVOKE = "api:key:revoke"
    API_RATE_LIMIT_OVERRIDE = "api:ratelimit:override"
    
    # Billing and Subscription
    BILLING_READ = "billing:read"
    BILLING_UPDATE = "billing:update"
    SUBSCRIPTION_MANAGE = "subscription:manage"
    
    # Organization Management
    ORG_CREATE = "org:create"
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"
    ORG_INVITE_MEMBER = "org:invite"
    ORG_REMOVE_MEMBER = "org:remove"


@dataclass
class Role:
    """Role definition with permissions"""
    name: str
    description: str
    permissions: Set[Permission] = field(default_factory=set)
    parent_roles: Set[str] = field(default_factory=set)  # For role hierarchy
    is_system: bool = False  # System roles cannot be modified
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ResourcePolicy:
    """Resource-based access policy"""
    resource_type: str  # e.g., "content", "analytics", "integration"
    resource_id: str
    allowed_actions: Set[str]
    conditions: Dict[str, Any] = field(default_factory=dict)  # e.g., {"time_range": "business_hours"}
    expires_at: Optional[datetime] = None


class RBACManager:
    """Role-Based Access Control Manager"""
    
    # Default system roles
    SYSTEM_ROLES = {
        "super_admin": Role(
            name="super_admin",
            description="Super Administrator with full system access",
            permissions=set(Permission),  # All permissions
            is_system=True
        ),
        "admin": Role(
            name="admin",
            description="Organization Administrator",
            permissions={
                Permission.USER_CREATE, Permission.USER_READ, Permission.USER_UPDATE,
                Permission.USER_DELETE, Permission.USER_LIST,
                Permission.CONTENT_CREATE, Permission.CONTENT_READ, Permission.CONTENT_UPDATE,
                Permission.CONTENT_DELETE, Permission.CONTENT_PUBLISH, Permission.CONTENT_ANALYZE,
                Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT, Permission.ANALYTICS_CONFIGURE,
                Permission.INTEGRATION_CREATE, Permission.INTEGRATION_READ, Permission.INTEGRATION_UPDATE,
                Permission.INTEGRATION_DELETE, Permission.INTEGRATION_EXECUTE,
                Permission.API_KEY_CREATE, Permission.API_KEY_READ, Permission.API_KEY_REVOKE,
                Permission.ORG_READ, Permission.ORG_UPDATE, Permission.ORG_INVITE_MEMBER,
                Permission.ORG_REMOVE_MEMBER
            },
            is_system=True
        ),
        "developer": Role(
            name="developer",
            description="Developer with API and integration access",
            permissions={
                Permission.CONTENT_CREATE, Permission.CONTENT_READ, Permission.CONTENT_UPDATE,
                Permission.CONTENT_ANALYZE,
                Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT,
                Permission.INTEGRATION_CREATE, Permission.INTEGRATION_READ, Permission.INTEGRATION_UPDATE,
                Permission.INTEGRATION_EXECUTE,
                Permission.MODEL_READ,
                Permission.API_KEY_CREATE, Permission.API_KEY_READ
            },
            is_system=True
        ),
        "analyst": Role(
            name="analyst",
            description="Data Analyst with read-only access to analytics",
            permissions={
                Permission.CONTENT_READ,
                Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT,
                Permission.MODEL_READ
            },
            is_system=True
        ),
        "content_manager": Role(
            name="content_manager",
            description="Content Manager with full content access",
            permissions={
                Permission.CONTENT_CREATE, Permission.CONTENT_READ, Permission.CONTENT_UPDATE,
                Permission.CONTENT_DELETE, Permission.CONTENT_PUBLISH, Permission.CONTENT_ANALYZE,
                Permission.ANALYTICS_READ
            },
            is_system=True
        ),
        "viewer": Role(
            name="viewer",
            description="Read-only access to content and basic analytics",
            permissions={
                Permission.CONTENT_READ,
                Permission.ANALYTICS_READ
            },
            is_system=True
        )
    }
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self._initialize_system_roles()
    
    def _initialize_system_roles(self):
        """Initialize system roles in Redis"""
        for role_name, role in self.SYSTEM_ROLES.items():
            self._save_role(role)
    
    def _save_role(self, role: Role):
        """Save role to Redis"""
        key = f"rbac:role:{role.name}"
        value = {
            "name": role.name,
            "description": role.description,
            "permissions": [p.value for p in role.permissions],
            "parent_roles": list(role.parent_roles),
            "is_system": role.is_system,
            "created_at": role.created_at.isoformat(),
            "updated_at": role.updated_at.isoformat()
        }
        self.redis_client.set(key, json.dumps(value))
    
    def create_role(
        self,
        name: str,
        description: str,
        permissions: Set[Permission],
        parent_roles: Optional[Set[str]] = None
    ) -> Role:
        """Create a custom role
        
        Args:
            name: Role name
            description: Role description
            permissions: Set of permissions
            parent_roles: Parent roles to inherit from
            
        Returns:
            Created role
        """
        if self.get_role(name):
            raise ValueError(f"Role {name} already exists")
        
        role = Role(
            name=name,
            description=description,
            permissions=permissions,
            parent_roles=parent_roles or set(),
            is_system=False
        )
        
        self._save_role(role)
        logger.info(f"Created role: {name}")
        return role
    
    @lru_cache(maxsize=128)
    def get_role(self, name: str) -> Optional[Role]:
        """Get role by name"""
        key = f"rbac:role:{name}"
        data = self.redis_client.get(key)
        
        if not data:
            return None
        
        role_data = json.loads(data)
        return Role(
            name=role_data["name"],
            description=role_data["description"],
            permissions={Permission(p) for p in role_data["permissions"]},
            parent_roles=set(role_data["parent_roles"]),
            is_system=role_data["is_system"],
            created_at=datetime.fromisoformat(role_data["created_at"]),
            updated_at=datetime.fromisoformat(role_data["updated_at"])
        )
    
    def assign_role(self, user_id: str, role_name: str, org_id: Optional[str] = None):
        """Assign role to user
        
        Args:
            user_id: User identifier
            role_name: Role name to assign
            org_id: Optional organization ID for org-specific roles
        """
        role = self.get_role(role_name)
        if not role:
            raise ValueError(f"Role {role_name} not found")
        
        key = f"rbac:user:{user_id}:roles"
        if org_id:
            key = f"rbac:user:{user_id}:org:{org_id}:roles"
        
        self.redis_client.sadd(key, role_name)
        logger.info(f"Assigned role {role_name} to user {user_id}")
    
    def revoke_role(self, user_id: str, role_name: str, org_id: Optional[str] = None):
        """Revoke role from user
        
        Args:
            user_id: User identifier
            role_name: Role name to revoke
            org_id: Optional organization ID
        """
        key = f"rbac:user:{user_id}:roles"
        if org_id:
            key = f"rbac:user:{user_id}:org:{org_id}:roles"
        
        self.redis_client.srem(key, role_name)
        logger.info(f"Revoked role {role_name} from user {user_id}")
    
    def get_user_roles(self, user_id: str, org_id: Optional[str] = None) -> Set[Role]:
        """Get all roles assigned to user
        
        Args:
            user_id: User identifier
            org_id: Optional organization ID
            
        Returns:
            Set of roles
        """
        key = f"rbac:user:{user_id}:roles"
        if org_id:
            key = f"rbac:user:{user_id}:org:{org_id}:roles"
        
        role_names = self.redis_client.smembers(key)
        roles = set()
        
        for role_name in role_names:
            role_name = role_name.decode() if isinstance(role_name, bytes) else role_name
            role = self.get_role(role_name)
            if role:
                roles.add(role)
                # Add parent roles recursively
                roles.update(self._get_parent_roles(role))
        
        return roles
    
    def _get_parent_roles(self, role: Role) -> Set[Role]:
        """Get all parent roles recursively"""
        parent_roles = set()
        for parent_name in role.parent_roles:
            parent_role = self.get_role(parent_name)
            if parent_role:
                parent_roles.add(parent_role)
                parent_roles.update(self._get_parent_roles(parent_role))
        return parent_roles
    
    def get_user_permissions(self, user_id: str, org_id: Optional[str] = None) -> Set[Permission]:
        """Get all permissions for user
        
        Args:
            user_id: User identifier
            org_id: Optional organization ID
            
        Returns:
            Set of permissions
        """
        roles = self.get_user_roles(user_id, org_id)
        permissions = set()
        
        for role in roles:
            permissions.update(role.permissions)
        
        return permissions
    
    def has_permission(
        self,
        user_id: str,
        permission: Permission,
        org_id: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> bool:
        """Check if user has specific permission
        
        Args:
            user_id: User identifier
            permission: Permission to check
            org_id: Optional organization ID
            resource_id: Optional resource ID for resource-based checks
            
        Returns:
            True if user has permission
        """
        # Check role-based permissions
        user_permissions = self.get_user_permissions(user_id, org_id)
        if permission in user_permissions:
            return True
        
        # Check resource-based permissions if resource_id provided
        if resource_id:
            return self._check_resource_permission(user_id, permission, resource_id)
        
        return False
    
    def grant_resource_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        actions: Set[str],
        conditions: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ):
        """Grant resource-specific access to user
        
        Args:
            user_id: User identifier
            resource_type: Type of resource
            resource_id: Resource identifier
            actions: Allowed actions
            conditions: Optional conditions
            expires_at: Optional expiration time
        """
        policy = ResourcePolicy(
            resource_type=resource_type,
            resource_id=resource_id,
            allowed_actions=actions,
            conditions=conditions or {},
            expires_at=expires_at
        )
        
        key = f"rbac:user:{user_id}:resource:{resource_type}:{resource_id}"
        value = {
            "resource_type": policy.resource_type,
            "resource_id": policy.resource_id,
            "allowed_actions": list(policy.allowed_actions),
            "conditions": policy.conditions,
            "expires_at": policy.expires_at.isoformat() if policy.expires_at else None
        }
        
        if expires_at:
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            self.redis_client.setex(key, ttl, json.dumps(value))
        else:
            self.redis_client.set(key, json.dumps(value))
        
        logger.info(f"Granted resource access: user={user_id}, resource={resource_type}:{resource_id}")
    
    def _check_resource_permission(
        self,
        user_id: str,
        permission: Permission,
        resource_id: str
    ) -> bool:
        """Check resource-specific permission"""
        # Extract resource type from permission
        resource_type = permission.value.split(":")[0]
        action = permission.value.split(":")[1]
        
        key = f"rbac:user:{user_id}:resource:{resource_type}:{resource_id}"
        data = self.redis_client.get(key)
        
        if not data:
            return False
        
        policy_data = json.loads(data)
        
        # Check if action is allowed
        if action not in policy_data["allowed_actions"]:
            return False
        
        # Check conditions
        if policy_data["conditions"]:
            # Implement condition checking logic here
            # For now, we'll assume conditions are met
            pass
        
        return True
    
    def revoke_resource_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str
    ):
        """Revoke resource-specific access"""
        key = f"rbac:user:{user_id}:resource:{resource_type}:{resource_id}"
        self.redis_client.delete(key)
        logger.info(f"Revoked resource access: user={user_id}, resource={resource_type}:{resource_id}")
    
    def get_accessible_resources(
        self,
        user_id: str,
        resource_type: str
    ) -> List[str]:
        """Get all resources of a type accessible to user
        
        Args:
            user_id: User identifier
            resource_type: Type of resource
            
        Returns:
            List of resource IDs
        """
        pattern = f"rbac:user:{user_id}:resource:{resource_type}:*"
        resources = []
        
        for key in self.redis_client.scan_iter(match=pattern):
            # Extract resource ID from key
            parts = key.decode().split(":")
            if len(parts) >= 5:
                resources.append(parts[4])
        
        return resources