"""Tests for Multi-Factor Authentication (MFA) functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
import pyotp
import qrcode
from io import BytesIO

from src.models.user import User
from src.models.mfa import MFASecret, MFABackupCode, MFAMethod
from src.mfa.mfa_service import MFAService
from src.mfa.totp import TOTPService
from src.mfa.sms import SMSService
from src.mfa.email import EmailMFAService


class TestMFAModels:
    """Test MFA model functionality."""
    
    @pytest.mark.asyncio
    async def test_mfa_secret_creation(self, db, test_user: User):
        """Test MFA secret creation."""
        secret = MFASecret(
            user_id=test_user.id,
            method=MFAMethod.TOTP,
            secret=pyotp.random_base32(),
            is_active=True
        )
        
        db.add(secret)
        await db.commit()
        await db.refresh(secret)
        
        assert secret.id is not None
        assert secret.method == MFAMethod.TOTP
        assert secret.is_active is True
        assert len(secret.secret) > 0
    
    @pytest.mark.asyncio
    async def test_mfa_backup_code_creation(self, db, test_user: User):
        """Test MFA backup code creation."""
        codes = []
        for i in range(10):
            code = MFABackupCode(
                user_id=test_user.id,
                code=f"BACKUP{i:06d}",
                is_used=False
            )
            codes.append(code)
        
        db.add_all(codes)
        await db.commit()
        
        # Check codes were created
        user_codes = await db.query(MFABackupCode).filter(
            MFABackupCode.user_id == test_user.id
        ).all()
        
        assert len(user_codes) == 10
        assert all(not code.is_used for code in user_codes)


class TestTOTPService:
    """Test TOTP functionality."""
    
    @pytest.fixture
    def totp_service(self):
        """Create TOTP service instance."""
        return TOTPService()
    
    def test_generate_secret(self, totp_service: TOTPService):
        """Test TOTP secret generation."""
        secret = totp_service.generate_secret()
        
        assert secret is not None
        assert len(secret) == 32  # Base32 encoded
        assert secret.isalnum()
    
    def test_generate_provisioning_uri(self, totp_service: TOTPService):
        """Test TOTP provisioning URI generation."""
        secret = "JBSWY3DPEHPK3PXP"
        email = "user@example.com"
        
        uri = totp_service.generate_provisioning_uri(secret, email)
        
        assert uri.startswith("otpauth://totp/")
        assert "LLMOptimizer" in uri
        assert email in uri
        assert f"secret={secret}" in uri
    
    def test_generate_qr_code(self, totp_service: TOTPService):
        """Test QR code generation."""
        secret = "JBSWY3DPEHPK3PXP"
        email = "user@example.com"
        
        qr_code = totp_service.generate_qr_code(secret, email)
        
        assert qr_code is not None
        assert qr_code.startswith("data:image/png;base64,")
        
        # Verify it's valid base64
        import base64
        try:
            base64.b64decode(qr_code.split(",")[1])
        except Exception:
            pytest.fail("Invalid base64 QR code")
    
    def test_verify_token_valid(self, totp_service: TOTPService):
        """Test verifying valid TOTP token."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        current_token = totp.now()
        
        assert totp_service.verify_token(secret, current_token) is True
    
    def test_verify_token_invalid(self, totp_service: TOTPService):
        """Test verifying invalid TOTP token."""
        secret = pyotp.random_base32()
        
        assert totp_service.verify_token(secret, "000000") is False
        assert totp_service.verify_token(secret, "invalid") is False
        assert totp_service.verify_token(secret, "") is False
    
    def test_verify_token_with_window(self, totp_service: TOTPService):
        """Test TOTP token verification with time window."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate token for 30 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=30)
        past_token = totp.at(past_time)
        
        # Should be valid with default window
        assert totp_service.verify_token(secret, past_token) is True
        
        # Should be invalid with no window
        assert totp_service.verify_token(secret, past_token, valid_window=0) is False


class TestMFAService:
    """Test MFA service functionality."""
    
    @pytest.fixture
    def mfa_service(self, db):
        """Create MFA service instance."""
        return MFAService(db)
    
    @pytest.mark.asyncio
    async def test_enable_totp(self, mfa_service: MFAService, test_user: User):
        """Test enabling TOTP for user."""
        secret, qr_code, backup_codes = await mfa_service.enable_totp(test_user)
        
        assert secret is not None
        assert len(secret) == 32
        assert qr_code.startswith("data:image/png;base64,")
        assert len(backup_codes) == 10
        assert all(len(code) == 8 for code in backup_codes)
        
        # Check user MFA is enabled
        assert test_user.mfa_enabled is True
        assert test_user.mfa_methods == [MFAMethod.TOTP]
    
    @pytest.mark.asyncio
    async def test_verify_totp(
        self,
        mfa_service: MFAService,
        user_with_mfa: User,
        db
    ):
        """Test verifying TOTP token."""
        # Get user's TOTP secret
        mfa_secret = await db.query(MFASecret).filter(
            MFASecret.user_id == user_with_mfa.id,
            MFASecret.method == MFAMethod.TOTP
        ).first()
        
        # Generate valid token
        totp = pyotp.TOTP(mfa_secret.secret)
        valid_token = totp.now()
        
        # Verify token
        result = await mfa_service.verify_totp(user_with_mfa, valid_token)
        assert result is True
        
        # Verify invalid token
        result = await mfa_service.verify_totp(user_with_mfa, "000000")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_enable_sms(
        self,
        mfa_service: MFAService,
        test_user: User,
        mock_sms_service
    ):
        """Test enabling SMS MFA."""
        phone_number = "+1234567890"
        
        with patch.object(SMSService, "send_verification_code", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await mfa_service.enable_sms(test_user, phone_number)
            assert result is True
            
            # Check SMS was sent
            mock_send.assert_called_once()
            
            # Check user settings
            assert test_user.phone_number == phone_number
            assert MFAMethod.SMS in test_user.mfa_methods
    
    @pytest.mark.asyncio
    async def test_verify_sms(
        self,
        mfa_service: MFAService,
        test_user: User,
        redis_client
    ):
        """Test verifying SMS code."""
        test_user.phone_number = "+1234567890"
        test_user.mfa_methods = [MFAMethod.SMS]
        code = "123456"
        
        # Store code in Redis
        await redis_client.setex(
            f"mfa:sms:{test_user.id}",
            300,
            code
        )
        
        # Verify correct code
        result = await mfa_service.verify_sms(test_user, code)
        assert result is True
        
        # Code should be deleted after use
        stored_code = await redis_client.get(f"mfa:sms:{test_user.id}")
        assert stored_code is None
        
        # Verify incorrect code
        await redis_client.setex(f"mfa:sms:{test_user.id}", 300, "654321")
        result = await mfa_service.verify_sms(test_user, "111111")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_enable_email(
        self,
        mfa_service: MFAService,
        test_user: User,
        mock_email_service
    ):
        """Test enabling email MFA."""
        with patch.object(EmailMFAService, "send_verification_code", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await mfa_service.enable_email(test_user)
            assert result is True
            
            # Check email was sent
            mock_send.assert_called_once_with(test_user.email)
            
            # Check user settings
            assert MFAMethod.EMAIL in test_user.mfa_methods
    
    @pytest.mark.asyncio
    async def test_verify_backup_code(
        self,
        mfa_service: MFAService,
        user_with_mfa: User,
        db
    ):
        """Test verifying backup code."""
        # Get user's backup codes
        backup_codes = await db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_with_mfa.id,
            MFABackupCode.is_used == False
        ).all()
        
        assert len(backup_codes) > 0
        
        # Use first backup code
        code = backup_codes[0].code
        result = await mfa_service.verify_backup_code(user_with_mfa, code)
        assert result is True
        
        # Code should be marked as used
        await db.refresh(backup_codes[0])
        assert backup_codes[0].is_used is True
        assert backup_codes[0].used_at is not None
        
        # Cannot reuse the same code
        result = await mfa_service.verify_backup_code(user_with_mfa, code)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_regenerate_backup_codes(
        self,
        mfa_service: MFAService,
        user_with_mfa: User,
        db
    ):
        """Test regenerating backup codes."""
        # Get original codes
        original_codes = await db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_with_mfa.id
        ).all()
        original_count = len(original_codes)
        
        # Regenerate codes
        new_codes = await mfa_service.regenerate_backup_codes(user_with_mfa)
        
        assert len(new_codes) == 10
        
        # Check old codes are deleted
        old_codes = await db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_with_mfa.id,
            MFABackupCode.code.in_([c.code for c in original_codes])
        ).all()
        assert len(old_codes) == 0
        
        # Check new codes exist
        current_codes = await db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_with_mfa.id
        ).all()
        assert len(current_codes) == 10
    
    @pytest.mark.asyncio
    async def test_disable_mfa(
        self,
        mfa_service: MFAService,
        user_with_mfa: User,
        db
    ):
        """Test disabling MFA."""
        # Disable MFA
        await mfa_service.disable_mfa(user_with_mfa)
        
        # Check user settings
        assert user_with_mfa.mfa_enabled is False
        assert user_with_mfa.mfa_methods == []
        
        # Check secrets are deleted
        secrets = await db.query(MFASecret).filter(
            MFASecret.user_id == user_with_mfa.id
        ).all()
        assert len(secrets) == 0
        
        # Check backup codes are deleted
        codes = await db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_with_mfa.id
        ).all()
        assert len(codes) == 0


class TestMFAIntegration:
    """Integration tests for MFA functionality."""
    
    @pytest.mark.asyncio
    async def test_login_with_mfa(
        self,
        test_client,
        user_with_mfa: User,
        db
    ):
        """Test login flow with MFA enabled."""
        # First login attempt
        response = test_client.post("/api/v1/auth/login", data={
            "username": user_with_mfa.email,
            "password": "Test123!@#"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should get MFA token instead of access token
        assert "mfa_token" in data
        assert "mfa_required" in data
        assert data["mfa_required"] is True
        assert "access_token" not in data
        
        # Get TOTP secret
        mfa_secret = await db.query(MFASecret).filter(
            MFASecret.user_id == user_with_mfa.id,
            MFASecret.method == MFAMethod.TOTP
        ).first()
        
        # Generate valid TOTP
        totp = pyotp.TOTP(mfa_secret.secret)
        valid_code = totp.now()
        
        # Complete MFA
        mfa_response = test_client.post("/api/v1/auth/mfa/verify", json={
            "mfa_token": data["mfa_token"],
            "code": valid_code,
            "method": "totp"
        })
        
        assert mfa_response.status_code == 200
        mfa_data = mfa_response.json()
        
        assert "access_token" in mfa_data
        assert "refresh_token" in mfa_data
    
    @pytest.mark.asyncio
    async def test_enable_mfa_endpoint(
        self,
        test_client,
        test_user: User,
        auth_headers: dict
    ):
        """Test enabling MFA through API."""
        # Enable TOTP
        response = test_client.post(
            "/api/v1/mfa/totp/enable",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "secret" in data
        assert "qr_code" in data
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 10
    
    @pytest.mark.asyncio
    async def test_mfa_methods_endpoint(
        self,
        test_client,
        user_with_mfa: User,
        auth_headers: dict
    ):
        """Test listing MFA methods."""
        response = test_client.get(
            "/api/v1/mfa/methods",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        methods = response.json()
        
        assert "totp" in methods
        assert methods["totp"]["enabled"] is True
        assert methods["sms"]["enabled"] is False
        assert methods["email"]["enabled"] is False
    
    @pytest.mark.asyncio
    async def test_backup_codes_endpoint(
        self,
        test_client,
        user_with_mfa: User,
        auth_headers: dict
    ):
        """Test backup codes management."""
        # Get remaining codes
        response = test_client.get(
            "/api/v1/mfa/backup-codes",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["remaining"] == 10
        
        # Regenerate codes
        regen_response = test_client.post(
            "/api/v1/mfa/backup-codes/regenerate",
            headers=auth_headers
        )
        
        assert regen_response.status_code == 200
        new_codes = regen_response.json()["codes"]
        assert len(new_codes) == 10