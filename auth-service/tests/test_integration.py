"""Integration tests for complete authentication flows."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
import pyotp
import json

from src.models.user import User, UserStatus
from src.models.rbac import Role, Permission, UserRole, RolePermission
from src.models.mfa import MFASecret, MFAMethod
from src.models.session import UserSession


class TestCompleteAuthFlow:
    """Test complete authentication flows."""
    
    @pytest.mark.asyncio
    async def test_complete_registration_flow(
        self,
        test_client,
        mock_email_service,
        db
    ):
        """Test complete user registration flow."""
        # 1. Register new user
        registration_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123!@#",
            "full_name": "New User",
            "accept_terms": True
        }
        
        response = test_client.post(
            "/api/v1/auth/register",
            json=registration_data
        )
        
        assert response.status_code == 201
        user_data = response.json()
        
        assert user_data["email"] == registration_data["email"]
        assert user_data["email_verified"] is False
        
        # 2. Check verification email was sent
        assert len(mock_email_service) == 1
        assert mock_email_service[0]["to"] == registration_data["email"]
        assert "verify" in mock_email_service[0]["subject"].lower()
        
        # 3. Extract verification token from email
        # In real scenario, this would be extracted from email body
        user = await db.query(User).filter(
            User.email == registration_data["email"]
        ).first()
        
        from src.security.tokens import TokenService
        token_service = TokenService()
        verification_token = token_service.create_email_verification_token(user.email)
        
        # 4. Verify email
        verify_response = test_client.post(
            "/api/v1/users/verify-email",
            params={"token": verification_token}
        )
        
        assert verify_response.status_code == 200
        
        # 5. Login with verified account
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": registration_data["email"],
            "password": registration_data["password"]
        })
        
        assert login_response.status_code == 200
        tokens = login_response.json()
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        
        # 6. Access protected endpoint
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        profile_response = test_client.get("/api/v1/users/me", headers=headers)
        
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["email_verified"] is True
    
    @pytest.mark.asyncio
    async def test_complete_mfa_flow(
        self,
        test_client,
        test_user: User,
        db
    ):
        """Test complete MFA setup and authentication flow."""
        # 1. Login without MFA
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        assert login_response.status_code == 200
        tokens = login_response.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        
        # 2. Enable TOTP MFA
        enable_response = test_client.post(
            "/api/v1/mfa/totp/enable",
            headers=headers
        )
        
        assert enable_response.status_code == 200
        mfa_data = enable_response.json()
        
        totp_secret = mfa_data["secret"]
        backup_codes = mfa_data["backup_codes"]
        
        assert len(backup_codes) == 10
        
        # 3. Confirm TOTP setup
        totp = pyotp.TOTP(totp_secret)
        confirm_response = test_client.post(
            "/api/v1/mfa/totp/confirm",
            headers=headers,
            json={"code": totp.now()}
        )
        
        assert confirm_response.status_code == 200
        
        # 4. Logout
        logout_response = test_client.post("/api/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 200
        
        # 5. Login with MFA required
        mfa_login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        assert mfa_login_response.status_code == 200
        mfa_login_data = mfa_login_response.json()
        
        assert "mfa_token" in mfa_login_data
        assert "mfa_required" in mfa_login_data
        assert mfa_login_data["mfa_required"] is True
        
        # 6. Complete MFA verification
        mfa_verify_response = test_client.post("/api/v1/auth/mfa/verify", json={
            "mfa_token": mfa_login_data["mfa_token"],
            "code": totp.now(),
            "method": "totp"
        })
        
        assert mfa_verify_response.status_code == 200
        final_tokens = mfa_verify_response.json()
        
        assert "access_token" in final_tokens
        assert "refresh_token" in final_tokens
        
        # 7. Access protected resource with MFA-verified session
        mfa_headers = {"Authorization": f"Bearer {final_tokens['access_token']}"}
        protected_response = test_client.get("/api/v1/users/me", headers=mfa_headers)
        
        assert protected_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_complete_oauth_flow(
        self,
        test_client,
        redis_client,
        db
    ):
        """Test complete OAuth authentication flow."""
        # 1. Initiate OAuth flow
        oauth_init_response = test_client.get("/api/v1/auth/oauth/google/authorize")
        
        assert oauth_init_response.status_code == 307
        location = oauth_init_response.headers["location"]
        
        # Extract state from redirect URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(location)
        state = parse_qs(parsed.query)["state"][0]
        
        # 2. Simulate OAuth provider callback
        with patch("src.oauth.providers.GoogleOAuthProvider.exchange_code_for_token") as mock_exchange:
            with patch("src.oauth.providers.GoogleOAuthProvider.get_user_info") as mock_user_info:
                mock_exchange.return_value = {
                    "access_token": "google-access-token",
                    "refresh_token": "google-refresh-token",
                    "expires_in": 3600
                }
                
                mock_user_info.return_value = {
                    "id": "google-user-123",
                    "email": "oauth.user@gmail.com",
                    "name": "OAuth User",
                    "picture": "https://example.com/photo.jpg"
                }
                
                callback_response = test_client.get(
                    f"/api/v1/auth/oauth/google/callback",
                    params={"code": "test-auth-code", "state": state}
                )
                
                assert callback_response.status_code == 200
                oauth_tokens = callback_response.json()
                
                assert "access_token" in oauth_tokens
                assert "token_type" in oauth_tokens
        
        # 3. Use OAuth session to access protected resources
        oauth_headers = {"Authorization": f"Bearer {oauth_tokens['access_token']}"}
        profile_response = test_client.get("/api/v1/users/me", headers=oauth_headers)
        
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["email"] == "oauth.user@gmail.com"
    
    @pytest.mark.asyncio
    async def test_complete_saml_flow(
        self,
        test_client,
        redis_client,
        db
    ):
        """Test complete SAML SSO flow."""
        # 1. Initiate SAML SSO
        sso_init_response = test_client.get(
            "/api/v1/auth/saml/okta/login",
            params={"relay_state": "http://localhost:3000/dashboard"}
        )
        
        assert sso_init_response.status_code == 307
        sso_url = sso_init_response.headers["location"]
        
        # Extract SAML request details
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(sso_url)
        query_params = parse_qs(parsed.query)
        relay_state = query_params["RelayState"][0]
        
        # 2. Simulate SAML IdP response
        mock_saml_response = base64.b64encode(b"""
        <samlp:Response>
            <saml:Assertion>
                <saml:Subject>
                    <saml:NameID>saml.user@company.com</saml:NameID>
                </saml:Subject>
                <saml:AttributeStatement>
                    <saml:Attribute Name="email">
                        <saml:AttributeValue>saml.user@company.com</saml:AttributeValue>
                    </saml:Attribute>
                </saml:AttributeStatement>
            </saml:Assertion>
        </samlp:Response>
        """).decode()
        
        with patch("src.saml.saml_utils.SAMLUtils.parse_saml_response") as mock_parse:
            with patch("src.saml.saml_utils.SAMLUtils.verify_signature") as mock_verify:
                mock_parse.return_value = {
                    "success": True,
                    "name_id": "saml.user@company.com",
                    "attributes": {
                        "email": ["saml.user@company.com"],
                        "name": ["SAML User"]
                    }
                }
                mock_verify.return_value = True
                
                acs_response = test_client.post(
                    "/api/v1/auth/saml/okta/acs",
                    data={
                        "SAMLResponse": mock_saml_response,
                        "RelayState": relay_state
                    }
                )
                
                assert acs_response.status_code == 200
                saml_tokens = acs_response.json()
                
                assert "access_token" in saml_tokens
        
        # 3. Access protected resources with SAML session
        saml_headers = {"Authorization": f"Bearer {saml_tokens['access_token']}"}
        profile_response = test_client.get("/api/v1/users/me", headers=saml_headers)
        
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["email"] == "saml.user@company.com"


class TestRBACIntegration:
    """Test RBAC integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_role_based_access_flow(
        self,
        test_client,
        db
    ):
        """Test complete role-based access control flow."""
        # 1. Create roles and permissions
        admin_role = Role(name="admin", display_name="Administrator")
        editor_role = Role(name="editor", display_name="Editor")
        viewer_role = Role(name="viewer", display_name="Viewer")
        
        permissions = [
            Permission(name="users.manage", resource_type="users", allowed_actions=["*"]),
            Permission(name="content.edit", resource_type="content", allowed_actions=["create", "update", "delete"]),
            Permission(name="content.view", resource_type="content", allowed_actions=["read"])
        ]
        
        db.add_all([admin_role, editor_role, viewer_role] + permissions)
        await db.flush()
        
        # Assign permissions to roles
        db.add(RolePermission(role_id=admin_role.id, permission_id=permissions[0].id))
        db.add(RolePermission(role_id=admin_role.id, permission_id=permissions[1].id))
        db.add(RolePermission(role_id=editor_role.id, permission_id=permissions[1].id))
        db.add(RolePermission(role_id=viewer_role.id, permission_id=permissions[2].id))
        
        # 2. Create users with different roles
        from src.security.passwords import PasswordService
        password_service = PasswordService()
        
        users = [
            User(
                email="admin@example.com",
                username="admin",
                password_hash=password_service.hash_password("Admin123!"),
                status=UserStatus.ACTIVE
            ),
            User(
                email="editor@example.com",
                username="editor",
                password_hash=password_service.hash_password("Editor123!"),
                status=UserStatus.ACTIVE
            ),
            User(
                email="viewer@example.com",
                username="viewer",
                password_hash=password_service.hash_password("Viewer123!"),
                status=UserStatus.ACTIVE
            )
        ]
        
        db.add_all(users)
        await db.flush()
        
        # Assign roles to users
        db.add(UserRole(user_id=users[0].id, role_id=admin_role.id, assigned_by=users[0].id))
        db.add(UserRole(user_id=users[1].id, role_id=editor_role.id, assigned_by=users[0].id))
        db.add(UserRole(user_id=users[2].id, role_id=viewer_role.id, assigned_by=users[0].id))
        
        await db.commit()
        
        # 3. Test access with different roles
        # Admin can access user management
        admin_login = test_client.post("/api/v1/auth/login", data={
            "username": "admin@example.com",
            "password": "Admin123!"
        })
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        users_response = test_client.get("/api/v1/users/", headers=admin_headers)
        assert users_response.status_code == 200
        
        # Editor cannot access user management
        editor_login = test_client.post("/api/v1/auth/login", data={
            "username": "editor@example.com",
            "password": "Editor123!"
        })
        editor_token = editor_login.json()["access_token"]
        editor_headers = {"Authorization": f"Bearer {editor_token}"}
        
        users_response = test_client.get("/api/v1/users/", headers=editor_headers)
        assert users_response.status_code == 403
        
        # Viewer cannot edit content (hypothetical endpoint)
        viewer_login = test_client.post("/api/v1/auth/login", data={
            "username": "viewer@example.com",
            "password": "Viewer123!"
        })
        viewer_token = viewer_login.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Would fail on content edit endpoint
        # assert content_edit_response.status_code == 403


class TestSecurityScenarios:
    """Test various security scenarios."""
    
    @pytest.mark.asyncio
    async def test_account_lockout_flow(
        self,
        test_client,
        test_user: User,
        db
    ):
        """Test account lockout after failed login attempts."""
        # 1. Make multiple failed login attempts
        for i in range(6):
            response = test_client.post("/api/v1/auth/login", data={
                "username": test_user.email,
                "password": "WrongPassword123!"
            })
            
            if i < 5:
                assert response.status_code == 401
            else:
                # Account should be locked after 5 attempts
                assert response.status_code == 401
                assert "locked" in response.json()["detail"].lower()
        
        # 2. Verify account is locked
        await db.refresh(test_user)
        assert test_user.status == UserStatus.LOCKED
        assert test_user.failed_login_attempts >= 5
        
        # 3. Try login with correct password (should still fail)
        response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        assert response.status_code == 401
        assert "locked" in response.json()["detail"].lower()
        
        # 4. Admin unlocks account
        admin_user = await db.query(User).filter(User.is_system_user == True).first()
        from src.security.tokens import TokenService
        token_service = TokenService()
        admin_token = token_service.create_access_token(str(admin_user.id))
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        unlock_response = test_client.post(
            f"/api/v1/users/{test_user.id}/unlock",
            headers=admin_headers
        )
        
        assert unlock_response.status_code == 200
        
        # 5. User can now login
        response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_password_reset_flow(
        self,
        test_client,
        test_user: User,
        mock_email_service,
        token_service,
        db
    ):
        """Test complete password reset flow."""
        # 1. Request password reset
        reset_request = test_client.post(
            "/api/v1/users/request-password-reset",
            json={"email": test_user.email}
        )
        
        assert reset_request.status_code == 200
        
        # 2. Check reset email was sent
        assert len(mock_email_service) == 1
        assert mock_email_service[0]["to"] == test_user.email
        
        # 3. Extract reset token (in real scenario from email)
        reset_token = token_service.create_password_reset_token(str(test_user.id))
        
        # 4. Reset password with token
        new_password = "NewSecurePass456!@#"
        reset_response = test_client.post(
            "/api/v1/users/reset-password",
            json={
                "token": reset_token,
                "new_password": new_password
            }
        )
        
        assert reset_response.status_code == 200
        
        # 5. Login with new password
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": new_password
        })
        
        assert login_response.status_code == 200
        
        # 6. Old password should not work
        old_login = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        assert old_login.status_code == 401
    
    @pytest.mark.asyncio
    async def test_session_hijacking_prevention(
        self,
        test_client,
        test_user: User,
        db
    ):
        """Test session hijacking prevention mechanisms."""
        # 1. Login from first device
        device1_response = test_client.post("/api/v1/auth/login", 
            data={
                "username": test_user.email,
                "password": "Test123!@#"
            },
            headers={
                "User-Agent": "Device1/1.0",
                "X-Device-Fingerprint": "device1-fingerprint"
            }
        )
        
        assert device1_response.status_code == 200
        device1_token = device1_response.json()["access_token"]
        
        # 2. Try to use token from different device
        device2_headers = {
            "Authorization": f"Bearer {device1_token}",
            "User-Agent": "Device2/1.0",
            "X-Device-Fingerprint": "device2-fingerprint"
        }
        
        hijack_response = test_client.get(
            "/api/v1/users/me",
            headers=device2_headers
        )
        
        # Should fail due to device mismatch
        assert hijack_response.status_code == 401
        
        # 3. Original device should still work
        device1_headers = {
            "Authorization": f"Bearer {device1_token}",
            "User-Agent": "Device1/1.0",
            "X-Device-Fingerprint": "device1-fingerprint"
        }
        
        valid_response = test_client.get(
            "/api/v1/users/me",
            headers=device1_headers
        )
        
        assert valid_response.status_code == 200