"""Tests for user management API functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from src.models.user import User, UserStatus
from src.models.rbac import Role, UserRole
from src.models.audit import AuditLog
from src.services.user import UserService


class TestUserAPI:
    """Test user management API endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_current_user(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test getting current user profile."""
        response = test_client.get("/api/v1/users/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert data["full_name"] == test_user.full_name
        assert "password_hash" not in data
    
    @pytest.mark.asyncio
    async def test_update_current_user(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test updating current user profile."""
        update_data = {
            "full_name": "Updated Name",
            "phone_number": "+1234567890",
            "metadata": {
                "timezone": "UTC",
                "language": "en"
            }
        }
        
        response = test_client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["full_name"] == "Updated Name"
        assert data["phone_number"] == "+1234567890"
        assert data["metadata"]["timezone"] == "UTC"
    
    @pytest.mark.asyncio
    async def test_change_password(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test changing user password."""
        response = test_client.post(
            "/api/v1/users/me/change-password",
            headers=auth_headers,
            json={
                "current_password": "Test123!@#",
                "new_password": "NewPass456!@#"
            }
        )
        
        assert response.status_code == 200
        
        # Try logging in with new password
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "NewPass456!@#"
        })
        
        assert login_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test changing password with wrong current password."""
        response = test_client.post(
            "/api/v1/users/me/change-password",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword123!",
                "new_password": "NewPass456!@#"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid current password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_list_users_admin(
        self,
        test_client,
        admin_user: User,
        admin_headers: dict,
        test_user: User,
        db
    ):
        """Test listing users as admin."""
        # Create additional users
        users = []
        for i in range(5):
            user = User(
                email=f"user{i}@example.com",
                username=f"user{i}",
                password_hash="dummy",
                status=UserStatus.ACTIVE
            )
            users.append(user)
        
        db.add_all(users)
        await db.commit()
        
        # List users
        response = test_client.get(
            "/api/v1/users/",
            headers=admin_headers,
            params={"page": 1, "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] >= 7  # admin + test_user + 5 new users
        assert len(data["users"]) <= 10
    
    @pytest.mark.asyncio
    async def test_list_users_non_admin(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test listing users as non-admin (should fail)."""
        response = test_client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_admin(
        self,
        test_client,
        admin_headers: dict,
        test_user: User
    ):
        """Test getting user by ID as admin."""
        response = test_client.get(
            f"/api/v1/users/{test_user.id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_self(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test getting own user info by ID."""
        response = test_client.get(
            f"/api/v1/users/{test_user.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_other(
        self,
        test_client,
        test_user: User,
        admin_user: User,
        auth_headers: dict
    ):
        """Test getting other user's info (should fail)."""
        response = test_client.get(
            f"/api/v1/users/{admin_user.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_update_user_admin(
        self,
        test_client,
        admin_headers: dict,
        test_user: User
    ):
        """Test updating user as admin."""
        response = test_client.patch(
            f"/api/v1/users/{test_user.id}",
            headers=admin_headers,
            json={
                "status": UserStatus.INACTIVE,
                "metadata": {"admin_note": "Account suspended"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == UserStatus.INACTIVE
        assert data["metadata"]["admin_note"] == "Account suspended"
    
    @pytest.mark.asyncio
    async def test_delete_user(
        self,
        test_client,
        admin_headers: dict,
        db
    ):
        """Test deleting user."""
        # Create user to delete
        user = User(
            email="delete@example.com",
            username="deleteuser",
            password_hash="dummy"
        )
        db.add(user)
        await db.commit()
        
        # Delete user
        response = test_client.delete(
            f"/api/v1/users/{user.id}",
            headers=admin_headers
        )
        
        assert response.status_code == 204
        
        # Verify user is deleted
        deleted_user = await db.get(User, user.id)
        assert deleted_user.status == UserStatus.DELETED
        assert deleted_user.deleted_at is not None
    
    @pytest.mark.asyncio
    async def test_lock_user(
        self,
        test_client,
        admin_headers: dict,
        test_user: User,
        db
    ):
        """Test locking user account."""
        response = test_client.post(
            f"/api/v1/users/{test_user.id}/lock",
            headers=admin_headers,
            params={"reason": "Security violation", "duration_hours": 24}
        )
        
        assert response.status_code == 200
        
        # Check user is locked
        await db.refresh(test_user)
        assert test_user.status == UserStatus.LOCKED
        assert test_user.locked_until is not None
        assert test_user.lock_reason == "Security violation"
    
    @pytest.mark.asyncio
    async def test_unlock_user(
        self,
        test_client,
        admin_headers: dict,
        test_user: User,
        db
    ):
        """Test unlocking user account."""
        # Lock user first
        test_user.status = UserStatus.LOCKED
        test_user.locked_until = datetime.utcnow() + timedelta(hours=24)
        test_user.lock_reason = "Test lock"
        await db.commit()
        
        # Unlock user
        response = test_client.post(
            f"/api/v1/users/{test_user.id}/unlock",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # Check user is unlocked
        await db.refresh(test_user)
        assert test_user.status == UserStatus.ACTIVE
        assert test_user.locked_until is None
        assert test_user.lock_reason is None
    
    @pytest.mark.asyncio
    async def test_verify_email(
        self,
        test_client,
        test_user: User,
        token_service,
        db
    ):
        """Test email verification."""
        # Set user as unverified
        test_user.email_verified = False
        await db.commit()
        
        # Create verification token
        token = token_service.create_email_verification_token(test_user.email)
        
        # Verify email
        response = test_client.post(
            "/api/v1/users/verify-email",
            params={"token": token}
        )
        
        assert response.status_code == 200
        
        # Check email is verified
        await db.refresh(test_user)
        assert test_user.email_verified is True
    
    @pytest.mark.asyncio
    async def test_request_password_reset(
        self,
        test_client,
        test_user: User,
        mock_email_service
    ):
        """Test requesting password reset."""
        response = test_client.post(
            "/api/v1/users/request-password-reset",
            json={"email": test_user.email}
        )
        
        assert response.status_code == 200
        
        # Check email was sent
        assert len(mock_email_service) == 1
        assert mock_email_service[0]["to"] == test_user.email
        assert "password reset" in mock_email_service[0]["subject"].lower()
    
    @pytest.mark.asyncio
    async def test_reset_password(
        self,
        test_client,
        test_user: User,
        token_service,
        db
    ):
        """Test resetting password."""
        # Create reset token
        token = token_service.create_password_reset_token(str(test_user.id))
        
        # Reset password
        response = test_client.post(
            "/api/v1/users/reset-password",
            json={
                "token": token,
                "new_password": "ResetPass789!@#"
            }
        )
        
        assert response.status_code == 200
        
        # Try logging in with new password
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "ResetPass789!@#"
        })
        
        assert login_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_user_sessions(
        self,
        test_client,
        test_user: User,
        auth_headers: dict,
        active_session
    ):
        """Test listing user sessions."""
        response = test_client.get(
            "/api/v1/users/me/sessions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        sessions = response.json()
        
        assert len(sessions) >= 1
        assert any(s["id"] == str(active_session.id) for s in sessions)
    
    @pytest.mark.asyncio
    async def test_revoke_session(
        self,
        test_client,
        test_user: User,
        auth_headers: dict,
        active_session,
        db
    ):
        """Test revoking user session."""
        response = test_client.delete(
            f"/api/v1/users/me/sessions/{active_session.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Check session is revoked
        await db.refresh(active_session)
        assert active_session.status == "revoked"


class TestUserService:
    """Test user service functionality."""
    
    @pytest.fixture
    def user_service(self, db):
        """Create user service instance."""
        return UserService(db)
    
    @pytest.mark.asyncio
    async def test_create_user(
        self,
        user_service: UserService,
        password_service,
        db
    ):
        """Test creating new user."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewUser123!@#",
            "full_name": "New User"
        }
        
        user = await user_service.create_user(**user_data)
        
        assert user.email == user_data["email"]
        assert user.username == user_data["username"]
        assert user.full_name == user_data["full_name"]
        assert password_service.verify_password(
            user_data["password"],
            user.password_hash
        )
    
    @pytest.mark.asyncio
    async def test_create_duplicate_user(
        self,
        user_service: UserService,
        test_user: User
    ):
        """Test creating user with duplicate email/username."""
        # Try duplicate email
        with pytest.raises(ValueError, match="already exists"):
            await user_service.create_user(
                email=test_user.email,
                username="different",
                password="Test123!@#"
            )
        
        # Try duplicate username
        with pytest.raises(ValueError, match="already exists"):
            await user_service.create_user(
                email="different@example.com",
                username=test_user.username,
                password="Test123!@#"
            )
    
    @pytest.mark.asyncio
    async def test_update_user_metadata(
        self,
        user_service: UserService,
        test_user: User
    ):
        """Test updating user metadata."""
        metadata = {
            "preferences": {
                "theme": "dark",
                "notifications": True
            }
        }
        
        updated_user = await user_service.update_user(
            test_user,
            metadata=metadata
        )
        
        assert updated_user.metadata["preferences"]["theme"] == "dark"
        assert updated_user.metadata["preferences"]["notifications"] is True
    
    @pytest.mark.asyncio
    async def test_user_activity_tracking(
        self,
        user_service: UserService,
        test_user: User,
        db
    ):
        """Test user activity tracking."""
        # Update last activity
        await user_service.update_last_activity(test_user)
        
        # Check activity was updated
        await db.refresh(test_user)
        assert test_user.last_active_at is not None
        assert (datetime.utcnow() - test_user.last_active_at).seconds < 5
    
    @pytest.mark.asyncio
    async def test_user_search(
        self,
        user_service: UserService,
        db
    ):
        """Test searching users."""
        # Create test users
        users = [
            User(
                email="john.doe@example.com",
                username="johndoe",
                full_name="John Doe",
                password_hash="dummy"
            ),
            User(
                email="jane.smith@example.com",
                username="janesmith",
                full_name="Jane Smith",
                password_hash="dummy"
            ),
            User(
                email="bob.johnson@example.com",
                username="bobjohnson",
                full_name="Bob Johnson",
                password_hash="dummy"
            )
        ]
        
        db.add_all(users)
        await db.commit()
        
        # Search by name
        results = await user_service.search_users("john")
        assert len(results) == 2  # John Doe and Bob Johnson
        
        # Search by email
        results = await user_service.search_users("jane.smith")
        assert len(results) == 1
        assert results[0].email == "jane.smith@example.com"