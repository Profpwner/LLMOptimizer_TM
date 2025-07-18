"""Time-based One-Time Password (TOTP) service."""

import pyotp
import qrcode
import io
import base64
from typing import Optional, Tuple
from datetime import datetime

from ..models.mfa import MFASetup
from ..config import settings


class TOTPService:
    """Service for managing TOTP authentication."""
    
    def __init__(self):
        self.issuer = "LLMOptimizer"
        self.digits = 6
        self.interval = 30  # seconds
        self.window = 1  # Allow 1 interval before/after
    
    def generate_secret(self) -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()
    
    def generate_provisioning_uri(
        self,
        secret: str,
        email: str,
        device_name: Optional[str] = None
    ) -> str:
        """Generate provisioning URI for QR code."""
        totp = pyotp.TOTP(secret, issuer=self.issuer)
        label = f"{email}"
        if device_name:
            label += f" ({device_name})"
        
        return totp.provisioning_uri(
            name=label,
            issuer_name=self.issuer
        )
    
    def generate_qr_code(self, provisioning_uri: str) -> str:
        """Generate QR code as base64 encoded image."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    def verify_token(
        self,
        secret: str,
        token: str,
        counter_offset: int = 0
    ) -> Tuple[bool, Optional[int]]:
        """Verify TOTP token."""
        totp = pyotp.TOTP(secret)
        
        # Check with time window
        for window_offset in range(-self.window, self.window + 1):
            if totp.verify(
                token,
                counter_offset=counter_offset + window_offset
            ):
                return True, window_offset
        
        return False, None
    
    def generate_backup_codes(self, count: int = 8) -> list[str]:
        """Generate backup codes."""
        from ..security.passwords import PasswordService
        return PasswordService.generate_recovery_codes(count)
    
    async def setup_totp(
        self,
        user_id: str,
        device_name: str = "Default",
        email: str = None
    ) -> dict:
        """Setup TOTP for a user."""
        # Generate secret
        secret = self.generate_secret()
        
        # Generate provisioning URI
        provisioning_uri = self.generate_provisioning_uri(
            secret,
            email or user_id,
            device_name
        )
        
        # Generate QR code
        qr_code = self.generate_qr_code(provisioning_uri)
        
        # Generate backup codes
        backup_codes = self.generate_backup_codes()
        
        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code": qr_code,
            "backup_codes": backup_codes,
            "device_name": device_name
        }
    
    def get_current_token(self, secret: str) -> str:
        """Get current TOTP token (for testing)."""
        totp = pyotp.TOTP(secret)
        return totp.now()
    
    def get_remaining_seconds(self) -> int:
        """Get remaining seconds for current TOTP interval."""
        return self.interval - (int(datetime.utcnow().timestamp()) % self.interval)