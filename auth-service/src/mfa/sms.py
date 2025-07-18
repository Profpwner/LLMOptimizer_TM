"""SMS-based Multi-Factor Authentication service."""

import secrets
from typing import Optional, Dict
from datetime import datetime, timedelta
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from ..config import settings


class SMSService:
    """Service for SMS-based authentication."""
    
    def __init__(self):
        self.enabled = (
            settings.ENABLE_SMS_MFA and
            settings.TWILIO_ACCOUNT_SID and
            settings.TWILIO_AUTH_TOKEN
        )
        
        if self.enabled:
            self.client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            self.from_number = settings.TWILIO_FROM_NUMBER
        else:
            self.client = None
            self.from_number = None
        
        self.code_length = 6
        self.code_validity_minutes = 5
        self.max_attempts = 3
        
        # In-memory storage for development (use Redis in production)
        self._verification_codes: Dict[str, Dict] = {}
    
    def is_enabled(self) -> bool:
        """Check if SMS service is enabled."""
        return self.enabled
    
    def generate_code(self) -> str:
        """Generate a random verification code."""
        return ''.join(secrets.choice('0123456789') for _ in range(self.code_length))
    
    async def send_verification_code(
        self,
        phone_number: str,
        user_id: Optional[str] = None,
        purpose: str = "verification"
    ) -> Dict[str, any]:
        """Send verification code via SMS."""
        if not self.enabled:
            raise ValueError("SMS service is not enabled")
        
        # Normalize phone number
        phone_number = self._normalize_phone_number(phone_number)
        
        # Generate code
        code = self.generate_code()
        
        # Store code (in production, use Redis)
        verification_key = f"{phone_number}:{purpose}"
        self._verification_codes[verification_key] = {
            "code": code,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "attempts": 0,
            "verified": False
        }
        
        # Compose message
        message = self._compose_message(code, purpose)
        
        try:
            # Send SMS
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone_number
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "phone_number": self._mask_phone_number(phone_number),
                "expires_in_seconds": self.code_validity_minutes * 60
            }
        
        except TwilioException as e:
            return {
                "success": False,
                "error": str(e),
                "phone_number": self._mask_phone_number(phone_number)
            }
    
    async def verify_code(
        self,
        phone_number: str,
        code: str,
        purpose: str = "verification",
        user_id: Optional[str] = None
    ) -> Dict[str, any]:
        """Verify SMS code."""
        # Normalize phone number
        phone_number = self._normalize_phone_number(phone_number)
        
        # Get stored verification
        verification_key = f"{phone_number}:{purpose}"
        verification = self._verification_codes.get(verification_key)
        
        if not verification:
            return {
                "success": False,
                "error": "No verification code found"
            }
        
        # Check expiration
        if datetime.utcnow() - verification["created_at"] > timedelta(minutes=self.code_validity_minutes):
            del self._verification_codes[verification_key]
            return {
                "success": False,
                "error": "Verification code expired"
            }
        
        # Check attempts
        verification["attempts"] += 1
        if verification["attempts"] > self.max_attempts:
            del self._verification_codes[verification_key]
            return {
                "success": False,
                "error": "Too many attempts"
            }
        
        # Check user ID if provided
        if user_id and verification.get("user_id") != user_id:
            return {
                "success": False,
                "error": "User mismatch"
            }
        
        # Verify code
        if verification["code"] == code:
            verification["verified"] = True
            del self._verification_codes[verification_key]
            return {
                "success": True,
                "phone_number": phone_number
            }
        else:
            return {
                "success": False,
                "error": "Invalid code",
                "attempts_remaining": self.max_attempts - verification["attempts"]
            }
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """Normalize phone number to E.164 format."""
        # Remove all non-digit characters
        digits = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if not present (assume US)
        if len(digits) == 10:
            digits = '1' + digits
        
        # Add + prefix
        if not digits.startswith('+'):
            digits = '+' + digits
        
        return digits
    
    def _mask_phone_number(self, phone_number: str) -> str:
        """Mask phone number for privacy."""
        if len(phone_number) < 4:
            return "****"
        
        # Show last 4 digits only
        return f"****{phone_number[-4:]}"
    
    def _compose_message(self, code: str, purpose: str) -> str:
        """Compose SMS message based on purpose."""
        messages = {
            "verification": f"Your LLMOptimizer verification code is: {code}",
            "login": f"Your LLMOptimizer login code is: {code}",
            "reset": f"Your LLMOptimizer password reset code is: {code}",
            "mfa": f"Your LLMOptimizer authentication code is: {code}"
        }
        
        message = messages.get(purpose, f"Your verification code is: {code}")
        message += f"\n\nThis code expires in {self.code_validity_minutes} minutes."
        
        return message
    
    async def send_alert(
        self,
        phone_number: str,
        alert_type: str,
        details: Optional[Dict] = None
    ) -> bool:
        """Send security alert via SMS."""
        if not self.enabled:
            return False
        
        # Normalize phone number
        phone_number = self._normalize_phone_number(phone_number)
        
        # Compose alert message
        messages = {
            "new_login": "New login to your LLMOptimizer account detected.",
            "password_changed": "Your LLMOptimizer password was changed.",
            "suspicious_activity": "Suspicious activity detected on your LLMOptimizer account."
        }
        
        message = messages.get(alert_type, "Security alert from LLMOptimizer.")
        
        if details:
            if "location" in details:
                message += f"\nLocation: {details['location']}"
            if "device" in details:
                message += f"\nDevice: {details['device']}"
        
        message += "\n\nIf this wasn't you, please secure your account immediately."
        
        try:
            self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone_number
            )
            return True
        except Exception:
            return False