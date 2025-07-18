"""Tests for session management functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
import json

from src.models.user import User
from src.models.session import UserSession, SessionStatus
from src.security.session_manager import SessionManager
from src.security.device_fingerprint import DeviceFingerprintService


class TestSessionModels:
    """Test session model functionality."""
    
    @pytest.mark.asyncio
    async def test_session_creation(self, db, test_user: User):
        """Test session creation and properties."""
        session = UserSession(
            user_id=test_user.id,
            session_token="test-session-token",
            refresh_token="test-refresh-token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test Browser",
            device_fingerprint="test-device-123",
            status="active"
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        assert session.id is not None
        assert session.user_id == test_user.id
        assert session.is_active() is True
        assert session.is_expired() is False
    
    @pytest.mark.asyncio
    async def test_session_expiration(self, db, test_user: User):
        """Test session expiration checking."""
        # Create expired session
        session = UserSession(
            user_id=test_user.id,
            session_token="expired-token",
            refresh_token="expired-refresh",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            ip_address="192.168.1.1",
            status="active"
        )
        
        db.add(session)
        await db.commit()
        
        assert session.is_expired() is True
        assert session.is_active() is False  # Expired sessions are not active
    
    @pytest.mark.asyncio
    async def test_session_status_tracking(self, db, test_user: User):
        """Test session status changes."""
        session = UserSession(
            user_id=test_user.id,
            session_token="status-test-token",
            refresh_token="status-test-refresh",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            status="active"
        )
        
        db.add(session)
        await db.commit()
        
        # Test different statuses
        assert session.is_active() is True
        
        session.status = "revoked"
        assert session.is_active() is False
        
        session.status = "expired"
        assert session.is_active() is False


class TestDeviceFingerprint:
    """Test device fingerprinting functionality."""
    
    @pytest.fixture
    def fingerprint_service(self):
        """Create device fingerprint service."""
        return DeviceFingerprintService()
    
    def test_generate_fingerprint(self, fingerprint_service: DeviceFingerprintService):
        """Test device fingerprint generation."""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ip_address = "192.168.1.100"
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br"
        }
        
        fingerprint = fingerprint_service.generate_fingerprint(
            user_agent=user_agent,
            ip_address=ip_address,
            headers=headers
        )
        
        assert fingerprint is not None
        assert isinstance(fingerprint, str)
        assert len(fingerprint) > 0
        
        # Same inputs should generate same fingerprint
        fingerprint2 = fingerprint_service.generate_fingerprint(
            user_agent=user_agent,
            ip_address=ip_address,
            headers=headers
        )
        
        assert fingerprint == fingerprint2
    
    def test_validate_fingerprint(self, fingerprint_service: DeviceFingerprintService):
        """Test device fingerprint validation."""
        stored_fingerprint = "stored-device-123"
        
        # Exact match
        assert fingerprint_service.validate_fingerprint(
            stored_fingerprint,
            stored_fingerprint
        ) is True
        
        # Different fingerprint
        assert fingerprint_service.validate_fingerprint(
            stored_fingerprint,
            "different-device-456"
        ) is False
    
    def test_extract_device_info(self, fingerprint_service: DeviceFingerprintService):
        """Test extracting device information."""
        user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15"
        
        device_info = fingerprint_service.extract_device_info(user_agent)
        
        assert device_info is not None
        assert "device" in device_info
        assert "os" in device_info
        assert "browser" in device_info


class TestSessionManager:
    """Test session manager functionality."""
    
    @pytest.fixture
    def session_manager(self, db, redis_client):
        """Create session manager instance."""
        return SessionManager(db, redis_client)
    
    @pytest.mark.asyncio
    async def test_create_session(
        self,
        session_manager: SessionManager,
        test_user: User,
        token_service
    ):
        """Test creating new session."""
        session_data = {
            "ip_address": "192.168.1.1",
            "user_agent": "Test Browser/1.0",
            "device_fingerprint": "test-device-123"
        }
        
        session, tokens = await session_manager.create_session(
            user=test_user,
            **session_data
        )
        
        assert session is not None
        assert session.user_id == test_user.id
        assert session.ip_address == "192.168.1.1"
        assert session.status == "active"
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_concurrent_session_limit(
        self,
        session_manager: SessionManager,
        test_user: User,
        db
    ):
        """Test enforcing concurrent session limits."""
        # Create multiple sessions
        for i in range(6):
            session = UserSession(
                user_id=test_user.id,
                session_token=f"token-{i}",
                refresh_token=f"refresh-{i}",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                ip_address=f"192.168.1.{i}",
                status="active"
            )
            db.add(session)
        
        await db.commit()
        
        # Create new session (should invalidate oldest)
        new_session, _ = await session_manager.create_session(
            user=test_user,
            ip_address="192.168.1.100",
            user_agent="New Browser"
        )
        
        # Check active sessions
        active_sessions = await session_manager.get_active_sessions(test_user)
        assert len(active_sessions) <= 5  # Max concurrent sessions
        
        # New session should be active
        assert any(s.id == new_session.id for s in active_sessions)
    
    @pytest.mark.asyncio
    async def test_validate_session(
        self,
        session_manager: SessionManager,
        active_session: UserSession
    ):
        """Test session validation."""
        # Valid session
        is_valid = await session_manager.validate_session(
            str(active_session.id),
            active_session.device_fingerprint
        )
        assert is_valid is True
        
        # Invalid session ID
        is_valid = await session_manager.validate_session(
            "invalid-session-id",
            active_session.device_fingerprint
        )
        assert is_valid is False
        
        # Wrong device fingerprint
        is_valid = await session_manager.validate_session(
            str(active_session.id),
            "wrong-device"
        )
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_refresh_session(
        self,
        session_manager: SessionManager,
        active_session: UserSession,
        test_user: User
    ):
        """Test refreshing session tokens."""
        old_refresh_token = active_session.refresh_token
        
        new_tokens = await session_manager.refresh_session(
            active_session,
            old_refresh_token
        )
        
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["refresh_token"] != old_refresh_token
        
        # Old refresh token should be invalidated
        await session_manager.redis.get(f"blacklist:token:{old_refresh_token}")
    
    @pytest.mark.asyncio
    async def test_revoke_session(
        self,
        session_manager: SessionManager,
        active_session: UserSession,
        db
    ):
        """Test revoking session."""
        await session_manager.revoke_session(active_session)
        
        # Check session is revoked
        await db.refresh(active_session)
        assert active_session.status == "revoked"
        assert active_session.revoked_at is not None
        
        # Tokens should be blacklisted
        assert await session_manager.redis.get(
            f"blacklist:token:{active_session.session_token}"
        ) is not None
    
    @pytest.mark.asyncio
    async def test_revoke_all_sessions(
        self,
        session_manager: SessionManager,
        test_user: User,
        db
    ):
        """Test revoking all user sessions."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = UserSession(
                user_id=test_user.id,
                session_token=f"revoke-all-{i}",
                refresh_token=f"revoke-all-refresh-{i}",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                status="active"
            )
            sessions.append(session)
        
        db.add_all(sessions)
        await db.commit()
        
        # Revoke all sessions
        await session_manager.revoke_all_sessions(test_user)
        
        # Check all sessions are revoked
        for session in sessions:
            await db.refresh(session)
            assert session.status == "revoked"
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(
        self,
        session_manager: SessionManager,
        test_user: User,
        db
    ):
        """Test cleaning up expired sessions."""
        # Create expired sessions
        expired_sessions = []
        for i in range(3):
            session = UserSession(
                user_id=test_user.id,
                session_token=f"expired-{i}",
                refresh_token=f"expired-refresh-{i}",
                expires_at=datetime.utcnow() - timedelta(hours=i+1),
                status="active"
            )
            expired_sessions.append(session)
        
        # Create active session
        active_session = UserSession(
            user_id=test_user.id,
            session_token="active-token",
            refresh_token="active-refresh",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            status="active"
        )
        
        db.add_all(expired_sessions + [active_session])
        await db.commit()
        
        # Cleanup expired sessions
        cleaned = await session_manager.cleanup_expired_sessions()
        assert cleaned >= 3
        
        # Check expired sessions are marked
        for session in expired_sessions:
            await db.refresh(session)
            assert session.status == "expired"
        
        # Active session should remain active
        await db.refresh(active_session)
        assert active_session.status == "active"
    
    @pytest.mark.asyncio
    async def test_session_activity_tracking(
        self,
        session_manager: SessionManager,
        active_session: UserSession,
        db
    ):
        """Test tracking session activity."""
        original_activity = active_session.last_activity
        original_count = active_session.request_count
        
        # Update activity
        await session_manager.update_session_activity(
            active_session,
            ip_address="192.168.1.2"
        )
        
        await db.refresh(active_session)
        
        assert active_session.last_activity > original_activity
        assert active_session.request_count == original_count + 1
        assert active_session.last_ip_address == "192.168.1.2"
    
    @pytest.mark.asyncio
    async def test_suspicious_activity_detection(
        self,
        session_manager: SessionManager,
        active_session: UserSession,
        db
    ):
        """Test detecting suspicious session activity."""
        # Simulate rapid location change
        active_session.ip_address = "192.168.1.1"
        active_session.location = {"country": "US", "city": "New York"}
        await db.commit()
        
        # Access from different location
        is_suspicious = await session_manager.check_suspicious_activity(
            active_session,
            ip_address="185.220.100.240",  # Different country IP
            user_agent=active_session.user_agent
        )
        
        assert is_suspicious is True
        
        # Mark session as suspicious
        await session_manager.mark_session_suspicious(
            active_session,
            reason="Location change detected"
        )
        
        await db.refresh(active_session)
        assert active_session.is_suspicious is True


class TestSessionIntegration:
    """Integration tests for session management."""
    
    @pytest.mark.asyncio
    async def test_login_creates_session(
        self,
        test_client,
        test_user: User,
        db
    ):
        """Test that login creates a session."""
        response = test_client.post("/api/v1/auth/login", 
            data={
                "username": test_user.email,
                "password": "Test123!@#"
            },
            headers={
                "User-Agent": "Test Browser/1.0",
                "X-Forwarded-For": "192.168.1.100"
            }
        )
        
        assert response.status_code == 200
        
        # Check session was created
        sessions = await db.query(UserSession).filter(
            UserSession.user_id == test_user.id
        ).all()
        
        assert len(sessions) > 0
        latest_session = sessions[-1]
        assert latest_session.user_agent == "Test Browser/1.0"
        assert latest_session.status == "active"
    
    @pytest.mark.asyncio
    async def test_logout_revokes_session(
        self,
        test_client,
        test_user: User,
        auth_headers: dict,
        active_session: UserSession,
        db
    ):
        """Test that logout revokes the session."""
        response = test_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Check session is revoked
        await db.refresh(active_session)
        assert active_session.status == "revoked"
    
    @pytest.mark.asyncio
    async def test_refresh_token_rotation(
        self,
        test_client,
        test_user: User,
        db
    ):
        """Test refresh token rotation."""
        # Login to get tokens
        login_response = test_client.post("/api/v1/auth/login", data={
            "username": test_user.email,
            "password": "Test123!@#"
        })
        
        tokens = login_response.json()
        old_refresh = tokens["refresh_token"]
        
        # Refresh tokens
        refresh_response = test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": old_refresh
        })
        
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        assert new_tokens["refresh_token"] != old_refresh
        
        # Old refresh token should not work
        second_refresh = test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": old_refresh
        })
        
        assert second_refresh.status_code == 401
    
    @pytest.mark.asyncio
    async def test_device_fingerprint_validation(
        self,
        test_client,
        test_user: User,
        auth_headers: dict,
        active_session: UserSession
    ):
        """Test device fingerprint validation."""
        # Access with correct device fingerprint
        response = test_client.get(
            "/api/v1/users/me",
            headers={
                **auth_headers,
                "X-Device-Fingerprint": active_session.device_fingerprint
            }
        )
        
        assert response.status_code == 200
        
        # Access with wrong device fingerprint
        response = test_client.get(
            "/api/v1/users/me",
            headers={
                **auth_headers,
                "X-Device-Fingerprint": "wrong-device-123"
            }
        )
        
        assert response.status_code == 401
        assert "Device mismatch" in response.json()["detail"]