"""Tests for JWT token functionality."""

import pytest
from datetime import datetime, timedelta, timezone
import jwt
from freezegun import freeze_time

from src.security.tokens import TokenService, TokenType, TokenData
from src.models.user import User
from src.models.session import UserSession


class TestTokenService:
    """Test JWT token service."""
    
    def test_create_access_token(self, token_service: TokenService):
        """Test access token creation."""
        user_id = "test-user-123"
        token = token_service.create_access_token(user_id)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token.split('.')) == 3  # JWT format
        
        # Decode and verify
        decoded = token_service.decode_token(token)
        assert decoded.sub == user_id
        assert decoded.type == TokenType.ACCESS
        assert decoded.exp > datetime.now(timezone.utc)
    
    def test_create_refresh_token(self, token_service: TokenService):
        """Test refresh token creation."""
        user_id = "test-user-123"
        token = token_service.create_refresh_token(user_id)
        
        assert token is not None
        assert isinstance(token, str)
        
        # Decode and verify
        decoded = token_service.decode_token(token)
        assert decoded.sub == user_id
        assert decoded.type == TokenType.REFRESH
        assert decoded.exp > datetime.now(timezone.utc)
    
    def test_create_mfa_token(self, token_service: TokenService):
        """Test MFA token creation."""
        user_id = "test-user-123"
        token = token_service.create_mfa_token(user_id)
        
        decoded = token_service.decode_token(token)
        assert decoded.sub == user_id
        assert decoded.type == TokenType.MFA
        assert decoded.exp > datetime.now(timezone.utc)
    
    def test_create_email_verification_token(self, token_service: TokenService):
        """Test email verification token creation."""
        email = "test@example.com"
        token = token_service.create_email_verification_token(email)
        
        decoded = token_service.decode_token(token)
        assert decoded.sub == email
        assert decoded.type == TokenType.EMAIL_VERIFICATION
        assert decoded.purpose == "email_verification"
    
    def test_create_password_reset_token(self, token_service: TokenService):
        """Test password reset token creation."""
        user_id = "test-user-123"
        token = token_service.create_password_reset_token(user_id)
        
        decoded = token_service.decode_token(token)
        assert decoded.sub == user_id
        assert decoded.type == TokenType.PASSWORD_RESET
        assert decoded.purpose == "password_reset"
    
    def test_token_with_custom_claims(self, token_service: TokenService):
        """Test token creation with custom claims."""
        user_id = "test-user-123"
        custom_claims = {
            "role": "admin",
            "permissions": ["read", "write"],
            "session_id": "session-456"
        }
        
        token = token_service.create_token(
            {"sub": user_id, **custom_claims},
            TokenType.ACCESS
        )
        
        decoded = token_service.decode_token(token)
        assert decoded.sub == user_id
        assert decoded.role == "admin"
        assert decoded.permissions == ["read", "write"]
        assert decoded.session_id == "session-456"
    
    def test_token_expiration(self, token_service: TokenService):
        """Test token expiration validation."""
        user_id = "test-user-123"
        
        # Create token with 1 second expiration
        token = token_service.create_token(
            {"sub": user_id},
            TokenType.ACCESS,
            expires_delta=timedelta(seconds=1)
        )
        
        # Should be valid immediately
        decoded = token_service.decode_token(token)
        assert decoded.sub == user_id
        
        # Should be expired after 2 seconds
        with freeze_time(datetime.utcnow() + timedelta(seconds=2)):
            with pytest.raises(ValueError, match="Token has expired"):
                token_service.decode_token(token)
    
    def test_token_type_validation(self, token_service: TokenService):
        """Test token type validation."""
        user_id = "test-user-123"
        access_token = token_service.create_access_token(user_id)
        refresh_token = token_service.create_refresh_token(user_id)
        
        # Verify correct type works
        token_service.verify_token(access_token, TokenType.ACCESS)
        token_service.verify_token(refresh_token, TokenType.REFRESH)
        
        # Verify wrong type fails
        with pytest.raises(ValueError, match="Invalid token type"):
            token_service.verify_token(access_token, TokenType.REFRESH)
        
        with pytest.raises(ValueError, match="Invalid token type"):
            token_service.verify_token(refresh_token, TokenType.ACCESS)
    
    def test_invalid_token_format(self, token_service: TokenService):
        """Test handling of invalid token formats."""
        invalid_tokens = [
            "not-a-jwt",
            "invalid.jwt.token",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",  # Missing parts
            "a.b.c.d",  # Too many parts
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises(ValueError):
                token_service.decode_token(invalid_token)
    
    def test_token_signature_tampering(self, token_service: TokenService):
        """Test detection of tampered tokens."""
        user_id = "test-user-123"
        token = token_service.create_access_token(user_id)
        
        # Tamper with payload
        parts = token.split('.')
        tampered_token = f"{parts[0]}.tampered.{parts[2]}"
        
        with pytest.raises(ValueError):
            token_service.decode_token(tampered_token)
    
    def test_token_with_wrong_secret(self, token_service: TokenService):
        """Test token signed with wrong secret."""
        fake_token = jwt.encode(
            {
                "sub": "user123",
                "type": "access",
                "exp": datetime.utcnow() + timedelta(hours=1)
            },
            "wrong_secret_key",
            algorithm="HS256"
        )
        
        with pytest.raises(ValueError):
            token_service.decode_token(fake_token)
    
    def test_token_blacklist_check(self, token_service: TokenService):
        """Test token blacklist functionality."""
        user_id = "test-user-123"
        token = token_service.create_access_token(user_id)
        jti = token_service.decode_token(token).jti
        
        # Token should be valid initially
        assert token_service.verify_token(token, TokenType.ACCESS) is not None
        
        # Add to blacklist
        token_service.blacklist_token(jti)
        
        # Token should now be invalid
        with pytest.raises(ValueError, match="Token has been revoked"):
            token_service.verify_token(token, TokenType.ACCESS)
    
    def test_refresh_token_rotation(self, token_service: TokenService):
        """Test refresh token rotation."""
        user_id = "test-user-123"
        old_refresh_token = token_service.create_refresh_token(user_id)
        
        # Use refresh token to get new tokens
        old_data = token_service.verify_token(old_refresh_token, TokenType.REFRESH)
        new_access_token = token_service.create_access_token(user_id)
        new_refresh_token = token_service.create_refresh_token(user_id)
        
        # Old refresh token should be blacklisted
        token_service.blacklist_token(old_data.jti)
        
        with pytest.raises(ValueError, match="Token has been revoked"):
            token_service.verify_token(old_refresh_token, TokenType.REFRESH)
        
        # New tokens should be valid
        token_service.verify_token(new_access_token, TokenType.ACCESS)
        token_service.verify_token(new_refresh_token, TokenType.REFRESH)
    
    @pytest.mark.asyncio
    async def test_token_with_session_binding(
        self,
        token_service: TokenService,
        active_session: UserSession
    ):
        """Test token bound to session."""
        token = token_service.create_token(
            {
                "sub": str(active_session.user_id),
                "session_id": str(active_session.id)
            },
            TokenType.ACCESS
        )
        
        decoded = token_service.decode_token(token)
        assert decoded.session_id == str(active_session.id)
        
        # If session is invalidated, token should also be invalid
        active_session.status = "revoked"
        # In real implementation, token validation would check session status


class TestTokenData:
    """Test TokenData model."""
    
    def test_token_data_creation(self):
        """Test TokenData object creation."""
        data = TokenData(
            sub="user123",
            type=TokenType.ACCESS,
            exp=datetime.utcnow() + timedelta(hours=1),
            iat=datetime.utcnow(),
            jti="unique-token-id"
        )
        
        assert data.sub == "user123"
        assert data.type == TokenType.ACCESS
        assert data.exp > datetime.utcnow()
    
    def test_token_data_from_dict(self):
        """Test TokenData creation from dictionary."""
        token_dict = {
            "sub": "user123",
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "jti": "unique-id",
            "custom_field": "custom_value"
        }
        
        data = TokenData(**token_dict)
        assert data.sub == "user123"
        assert data.type == "access"
        assert hasattr(data, "custom_field")
        assert data.custom_field == "custom_value"


class TestTokenIntegration:
    """Integration tests for token functionality."""
    
    @pytest.mark.asyncio
    async def test_login_token_flow(
        self,
        test_client,
        test_user: User,
        password_service
    ):
        """Test complete login token flow."""
        # Login
        response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        assert response.status_code == 200
        token_response = response.json()
        
        assert "access_token" in token_response
        assert "refresh_token" in token_response
        assert "token_type" in token_response
        assert token_response["token_type"] == "bearer"
        
        # Use access token
        headers = {"Authorization": f"Bearer {token_response['access_token']}"}
        profile_response = test_client.get("/api/v1/users/me", headers=headers)
        
        assert profile_response.status_code == 200
        assert profile_response.json()["email"] == test_user.email
    
    @pytest.mark.asyncio
    async def test_refresh_token_flow(
        self,
        test_client,
        test_user: User
    ):
        """Test refresh token flow."""
        # Login to get tokens
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_response = test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]
    
    @pytest.mark.asyncio
    async def test_logout_token_invalidation(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test token invalidation on logout."""
        # Verify token works before logout
        profile_response = test_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        assert profile_response.status_code == 200
        
        # Logout
        logout_response = test_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        assert logout_response.status_code == 200
        
        # Token should no longer work
        profile_response = test_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        assert profile_response.status_code == 401