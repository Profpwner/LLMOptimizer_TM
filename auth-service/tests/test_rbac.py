"""Tests for Role-Based Access Control (RBAC) functionality."""

import pytest
from datetime import datetime, timedelta

from src.models.rbac import Role, Permission, UserRole, RolePermission, RoleHierarchy
from src.models.user import User
from src.security.rbac import RBACService


class TestRBACModels:
    """Test RBAC model functionality."""
    
    @pytest.mark.asyncio
    async def test_role_creation(self, db):
        """Test role creation and properties."""
        role = Role(
            name="editor",
            display_name="Editor",
            description="Can edit content",
            priority=50
        )
        
        db.add(role)
        await db.commit()
        await db.refresh(role)
        
        assert role.id is not None
        assert role.name == "editor"
        assert role.display_name == "Editor"
        assert role.priority == 50
        assert role.is_active is True
    
    @pytest.mark.asyncio
    async def test_permission_creation(self, db):
        """Test permission creation and properties."""
        permission = Permission(
            name="content_edit",
            display_name="Edit Content",
            description="Allows editing content",
            resource_type="content",
            allowed_actions=["create", "read", "update", "delete"]
        )
        
        db.add(permission)
        await db.commit()
        await db.refresh(permission)
        
        assert permission.id is not None
        assert permission.resource_type == "content"
        assert "update" in permission.allowed_actions
        assert permission.allows_action("update") is True
        assert permission.allows_action("execute") is False
    
    @pytest.mark.asyncio
    async def test_wildcard_permission(self, db):
        """Test wildcard permission functionality."""
        permission = Permission(
            name="admin_all",
            display_name="Admin All",
            resource_type="*",
            allowed_actions=["*"]
        )
        
        # Should allow any action
        assert permission.allows_action("read") is True
        assert permission.allows_action("write") is True
        assert permission.allows_action("delete") is True
        assert permission.allows_action("anything") is True
    
    @pytest.mark.asyncio
    async def test_role_permission_assignment(self, db):
        """Test assigning permissions to roles."""
        # Create role and permissions
        role = Role(name="moderator", display_name="Moderator")
        permissions = [
            Permission(
                name="content_read",
                resource_type="content",
                allowed_actions=["read"]
            ),
            Permission(
                name="content_update",
                resource_type="content",
                allowed_actions=["update"]
            ),
            Permission(
                name="user_read",
                resource_type="user",
                allowed_actions=["read"]
            )
        ]
        
        db.add(role)
        db.add_all(permissions)
        await db.flush()
        
        # Assign permissions to role
        for permission in permissions:
            role_permission = RolePermission(
                role_id=role.id,
                permission_id=permission.id
            )
            db.add(role_permission)
        
        await db.commit()
        await db.refresh(role)
        
        # Check permissions
        role_permissions = role.get_all_permissions()
        assert len(role_permissions) == 3
        
        # Check specific permissions
        assert role.has_permission("content", "read")
        assert role.has_permission("content", "update")
        assert role.has_permission("user", "read")
        assert not role.has_permission("user", "delete")
    
    @pytest.mark.asyncio
    async def test_user_role_assignment(self, db, test_user: User):
        """Test assigning roles to users."""
        # Create roles
        editor_role = Role(name="editor", display_name="Editor")
        viewer_role = Role(name="viewer", display_name="Viewer")
        
        db.add_all([editor_role, viewer_role])
        await db.flush()
        
        # Assign roles to user
        user_roles = [
            UserRole(
                user_id=test_user.id,
                role_id=editor_role.id,
                assigned_by=test_user.id
            ),
            UserRole(
                user_id=test_user.id,
                role_id=viewer_role.id,
                assigned_by=test_user.id,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
        ]
        
        db.add_all(user_roles)
        await db.commit()
        await db.refresh(test_user)
        
        # Check user roles
        assert len(test_user.roles) == 2
        role_names = [role.name for role in test_user.roles]
        assert "editor" in role_names
        assert "viewer" in role_names
    
    @pytest.mark.asyncio
    async def test_role_hierarchy(self, db):
        """Test role hierarchy functionality."""
        # Create roles
        admin_role = Role(name="admin", display_name="Admin", priority=100)
        manager_role = Role(name="manager", display_name="Manager", priority=50)
        user_role = Role(name="user", display_name="User", priority=10)
        
        db.add_all([admin_role, manager_role, user_role])
        await db.flush()
        
        # Create hierarchy: admin > manager > user
        hierarchies = [
            RoleHierarchy(
                parent_role_id=admin_role.id,
                child_role_id=manager_role.id
            ),
            RoleHierarchy(
                parent_role_id=manager_role.id,
                child_role_id=user_role.id
            )
        ]
        
        db.add_all(hierarchies)
        await db.commit()
        
        # Admin should inherit all permissions from manager and user
        await db.refresh(admin_role)
        await db.refresh(manager_role)
        
        # Check hierarchy
        assert len(admin_role.child_roles) == 1
        assert admin_role.child_roles[0].id == manager_role.id
        assert len(manager_role.parent_roles) == 1
        assert manager_role.parent_roles[0].id == admin_role.id


class TestRBACService:
    """Test RBAC service functionality."""
    
    @pytest.fixture
    def rbac_service(self, db):
        """Create RBAC service instance."""
        return RBACService(db)
    
    @pytest.mark.asyncio
    async def test_create_role(self, rbac_service: RBACService):
        """Test creating role through service."""
        role = await rbac_service.create_role(
            name="contributor",
            display_name="Contributor",
            description="Can contribute content",
            permissions=["content:create", "content:read"]
        )
        
        assert role.name == "contributor"
        assert len(role.permissions) == 2
    
    @pytest.mark.asyncio
    async def test_assign_role_to_user(
        self,
        rbac_service: RBACService,
        test_user: User,
        admin_user: User,
        db
    ):
        """Test assigning role to user."""
        # Create role
        role = Role(name="premium", display_name="Premium User")
        db.add(role)
        await db.commit()
        
        # Assign role
        user_role = await rbac_service.assign_role_to_user(
            user=test_user,
            role=role,
            assigned_by=admin_user,
            expires_at=datetime.utcnow() + timedelta(days=365)
        )
        
        assert user_role.user_id == test_user.id
        assert user_role.role_id == role.id
        assert user_role.assigned_by == admin_user.id
        assert user_role.expires_at is not None
    
    @pytest.mark.asyncio
    async def test_revoke_role_from_user(
        self,
        rbac_service: RBACService,
        test_user: User,
        db
    ):
        """Test revoking role from user."""
        # Create and assign role
        role = Role(name="temp", display_name="Temporary")
        db.add(role)
        await db.flush()
        
        user_role = UserRole(
            user_id=test_user.id,
            role_id=role.id,
            assigned_by=test_user.id
        )
        db.add(user_role)
        await db.commit()
        
        # Revoke role
        await rbac_service.revoke_role_from_user(test_user, role)
        
        # Check role is revoked
        await db.refresh(test_user)
        role_names = [r.name for r in test_user.roles]
        assert "temp" not in role_names
    
    @pytest.mark.asyncio
    async def test_check_user_permission(
        self,
        rbac_service: RBACService,
        test_user: User,
        db
    ):
        """Test checking user permissions."""
        # Create role with permissions
        role = Role(name="author", display_name="Author")
        permission = Permission(
            name="article_write",
            resource_type="article",
            allowed_actions=["create", "update", "delete"]
        )
        
        db.add_all([role, permission])
        await db.flush()
        
        # Assign permission to role
        role_permission = RolePermission(
            role_id=role.id,
            permission_id=permission.id
        )
        db.add(role_permission)
        
        # Assign role to user
        user_role = UserRole(
            user_id=test_user.id,
            role_id=role.id,
            assigned_by=test_user.id
        )
        db.add(user_role)
        await db.commit()
        
        # Check permissions
        assert await rbac_service.user_has_permission(
            test_user, "article", "create"
        ) is True
        assert await rbac_service.user_has_permission(
            test_user, "article", "read"
        ) is False
        assert await rbac_service.user_has_permission(
            test_user, "video", "create"
        ) is False
    
    @pytest.mark.asyncio
    async def test_get_user_permissions(
        self,
        rbac_service: RBACService,
        admin_user: User
    ):
        """Test getting all user permissions."""
        permissions = await rbac_service.get_user_permissions(admin_user)
        
        assert len(permissions) > 0
        
        # Admin should have admin access permission
        permission_names = [p.name for p in permissions]
        assert "admin_access" in permission_names
    
    @pytest.mark.asyncio
    async def test_permission_inheritance(
        self,
        rbac_service: RBACService,
        test_user: User,
        db
    ):
        """Test permission inheritance through role hierarchy."""
        # Create parent and child roles
        parent_role = Role(name="parent", display_name="Parent")
        child_role = Role(name="child", display_name="Child")
        
        # Create permissions
        parent_permission = Permission(
            name="parent_perm",
            resource_type="resource",
            allowed_actions=["admin"]
        )
        child_permission = Permission(
            name="child_perm",
            resource_type="resource",
            allowed_actions=["read"]
        )
        
        db.add_all([parent_role, child_role, parent_permission, child_permission])
        await db.flush()
        
        # Assign permissions
        db.add(RolePermission(role_id=parent_role.id, permission_id=parent_permission.id))
        db.add(RolePermission(role_id=child_role.id, permission_id=child_permission.id))
        
        # Create hierarchy
        db.add(RoleHierarchy(parent_role_id=parent_role.id, child_role_id=child_role.id))
        
        # Assign parent role to user
        db.add(UserRole(user_id=test_user.id, role_id=parent_role.id, assigned_by=test_user.id))
        
        await db.commit()
        
        # User should have both permissions
        assert await rbac_service.user_has_permission(test_user, "resource", "admin") is True
        assert await rbac_service.user_has_permission(test_user, "resource", "read") is True


class TestRBACIntegration:
    """Integration tests for RBAC functionality."""
    
    @pytest.mark.asyncio
    async def test_permission_required_endpoint(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test endpoint that requires specific permission."""
        # Try to access admin endpoint without permission
        response = test_client.get("/api/v1/admin/users", headers=auth_headers)
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_admin_access_endpoint(
        self,
        test_client,
        admin_user: User,
        admin_headers: dict
    ):
        """Test admin accessing protected endpoint."""
        response = test_client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_role_assignment_api(
        self,
        test_client,
        test_user: User,
        admin_user: User,
        admin_headers: dict,
        db
    ):
        """Test role assignment through API."""
        # Create a role
        role = Role(name="vip", display_name="VIP User")
        db.add(role)
        await db.commit()
        
        # Assign role to user
        response = test_client.post(
            f"/api/v1/users/{test_user.id}/roles",
            headers=admin_headers,
            json={
                "role_id": str(role.id),
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["role"]["name"] == "vip"
        assert data["user_id"] == str(test_user.id)
    
    @pytest.mark.asyncio
    async def test_permission_check_api(
        self,
        test_client,
        test_user: User,
        auth_headers: dict,
        db
    ):
        """Test permission checking through API."""
        # Check permissions for current user
        response = test_client.get(
            "/api/v1/users/me/permissions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        permissions = response.json()
        assert isinstance(permissions, list)
    
    @pytest.mark.asyncio
    async def test_role_hierarchy_permissions(
        self,
        test_client,
        db
    ):
        """Test role hierarchy affects permissions."""
        # Create hierarchical roles
        ceo_role = Role(name="ceo", display_name="CEO", priority=1000)
        manager_role = Role(name="manager", display_name="Manager", priority=100)
        employee_role = Role(name="employee", display_name="Employee", priority=10)
        
        db.add_all([ceo_role, manager_role, employee_role])
        await db.flush()
        
        # Create permissions
        ceo_perm = Permission(name="company_manage", resource_type="company", allowed_actions=["*"])
        manager_perm = Permission(name="team_manage", resource_type="team", allowed_actions=["*"])
        employee_perm = Permission(name="task_manage", resource_type="task", allowed_actions=["read", "update"])
        
        db.add_all([ceo_perm, manager_perm, employee_perm])
        await db.flush()
        
        # Assign permissions
        db.add(RolePermission(role_id=ceo_role.id, permission_id=ceo_perm.id))
        db.add(RolePermission(role_id=manager_role.id, permission_id=manager_perm.id))
        db.add(RolePermission(role_id=employee_role.id, permission_id=employee_perm.id))
        
        # Create hierarchy
        db.add(RoleHierarchy(parent_role_id=ceo_role.id, child_role_id=manager_role.id))
        db.add(RoleHierarchy(parent_role_id=manager_role.id, child_role_id=employee_role.id))
        
        await db.commit()
        
        # CEO should have all permissions through inheritance
        ceo_permissions = ceo_role.get_all_permissions()
        assert len(ceo_permissions) == 3