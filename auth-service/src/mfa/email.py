"""Email-based Multi-Factor Authentication service."""

import secrets
from typing import Optional, Dict
from datetime import datetime, timedelta
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

from ..config import settings


class EmailMFAService:
    """Service for email-based authentication."""
    
    def __init__(self):
        self.enabled = (
            settings.SMTP_HOST and
            settings.SMTP_USERNAME and
            settings.SMTP_PASSWORD
        )
        
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_use_tls = settings.SMTP_USE_TLS
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME
        
        self.code_length = 6
        self.code_validity_minutes = 10
        self.max_attempts = 5
        
        # In-memory storage for development (use Redis in production)
        self._verification_codes: Dict[str, Dict] = {}
        
        # Email templates
        self.templates = self._load_templates()
    
    def is_enabled(self) -> bool:
        """Check if email service is enabled."""
        return self.enabled
    
    def generate_code(self) -> str:
        """Generate a random verification code."""
        return ''.join(secrets.choice('0123456789') for _ in range(self.code_length))
    
    async def send_verification_code(
        self,
        email: str,
        user_id: Optional[str] = None,
        purpose: str = "verification",
        user_name: Optional[str] = None
    ) -> Dict[str, any]:
        """Send verification code via email."""
        if not self.enabled:
            raise ValueError("Email service is not enabled")
        
        # Generate code
        code = self.generate_code()
        
        # Store code (in production, use Redis)
        verification_key = f"{email}:{purpose}"
        self._verification_codes[verification_key] = {
            "code": code,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "attempts": 0,
            "verified": False
        }
        
        # Send email
        subject = self._get_subject(purpose)
        html_content = self._render_template(
            purpose,
            code=code,
            user_name=user_name,
            validity_minutes=self.code_validity_minutes
        )
        
        success = await self._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content
        )
        
        return {
            "success": success,
            "email": self._mask_email(email),
            "expires_in_seconds": self.code_validity_minutes * 60
        }
    
    async def verify_code(
        self,
        email: str,
        code: str,
        purpose: str = "verification",
        user_id: Optional[str] = None
    ) -> Dict[str, any]:
        """Verify email code."""
        # Get stored verification
        verification_key = f"{email}:{purpose}"
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
                "email": email
            }
        else:
            return {
                "success": False,
                "error": "Invalid code",
                "attempts_remaining": self.max_attempts - verification["attempts"]
            }
    
    async def send_password_reset_link(
        self,
        email: str,
        reset_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """Send password reset email."""
        reset_url = f"{settings.PASSWORD_RESET_URL}?token={reset_token}"
        
        subject = "Reset Your LLMOptimizer Password"
        html_content = self.templates["password_reset"].render(
            user_name=user_name or "User",
            reset_url=reset_url,
            validity_hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )
        
        return await self._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content
        )
    
    async def send_verification_link(
        self,
        email: str,
        verification_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """Send email verification link."""
        verification_url = f"{settings.EMAIL_VERIFICATION_URL}?token={verification_token}"
        
        subject = "Verify Your LLMOptimizer Email"
        html_content = self.templates["email_verification"].render(
            user_name=user_name or "User",
            verification_url=verification_url
        )
        
        return await self._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content
        )
    
    async def send_security_alert(
        self,
        email: str,
        alert_type: str,
        details: Optional[Dict] = None,
        user_name: Optional[str] = None
    ) -> bool:
        """Send security alert email."""
        subject = "Security Alert - LLMOptimizer"
        html_content = self.templates["security_alert"].render(
            user_name=user_name or "User",
            alert_type=alert_type,
            details=details or {},
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        
        return await self._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content
        )
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email via SMTP."""
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Add text version if provided
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            # Add HTML version
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                use_tls=self.smtp_use_tls
            )
            
            return True
        
        except Exception as e:
            # Log error (in production)
            print(f"Email send error: {e}")
            return False
    
    def _mask_email(self, email: str) -> str:
        """Mask email for privacy."""
        parts = email.split('@')
        if len(parts) != 2:
            return "****"
        
        username, domain = parts
        if len(username) <= 3:
            masked_username = "****"
        else:
            masked_username = username[:2] + "****"
        
        return f"{masked_username}@{domain}"
    
    def _get_subject(self, purpose: str) -> str:
        """Get email subject based on purpose."""
        subjects = {
            "verification": "Your LLMOptimizer Verification Code",
            "login": "Your LLMOptimizer Login Code",
            "reset": "Your LLMOptimizer Password Reset Code",
            "mfa": "Your LLMOptimizer Authentication Code"
        }
        
        return subjects.get(purpose, "Your LLMOptimizer Verification Code")
    
    def _render_template(self, purpose: str, **context) -> str:
        """Render email template."""
        template_name = f"mfa_{purpose}"
        if template_name not in self.templates:
            template_name = "mfa_verification"
        
        return self.templates[template_name].render(**context)
    
    def _load_templates(self) -> Dict[str, Template]:
        """Load email templates."""
        templates = {}
        
        # MFA verification template
        templates["mfa_verification"] = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #007bff; color: white; padding: 20px; text-align: center; }
        .content { background-color: #f8f9fa; padding: 30px; margin-top: 20px; }
        .code { font-size: 32px; font-weight: bold; color: #007bff; text-align: center; padding: 20px; background-color: white; border: 2px solid #007bff; border-radius: 5px; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>LLMOptimizer</h1>
        </div>
        <div class="content">
            <h2>Hello {{ user_name|default('User') }},</h2>
            <p>Your verification code is:</p>
            <div class="code">{{ code }}</div>
            <p>This code expires in {{ validity_minutes }} minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 LLMOptimizer. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """)
        
        # Password reset template
        templates["password_reset"] = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #dc3545; color: white; padding: 20px; text-align: center; }
        .content { background-color: #f8f9fa; padding: 30px; margin-top: 20px; }
        .button { display: inline-block; padding: 12px 30px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Password Reset Request</h1>
        </div>
        <div class="content">
            <h2>Hello {{ user_name }},</h2>
            <p>We received a request to reset your password. Click the button below to create a new password:</p>
            <div style="text-align: center;">
                <a href="{{ reset_url }}" class="button">Reset Password</a>
            </div>
            <p>This link expires in {{ validity_hours }} hours.</p>
            <p>If you didn't request this, please ignore this email and your password will remain unchanged.</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 LLMOptimizer. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """)
        
        # Email verification template
        templates["email_verification"] = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #28a745; color: white; padding: 20px; text-align: center; }
        .content { background-color: #f8f9fa; padding: 30px; margin-top: 20px; }
        .button { display: inline-block; padding: 12px 30px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Verify Your Email</h1>
        </div>
        <div class="content">
            <h2>Welcome {{ user_name }}!</h2>
            <p>Thank you for signing up with LLMOptimizer. Please verify your email address by clicking the button below:</p>
            <div style="text-align: center;">
                <a href="{{ verification_url }}" class="button">Verify Email</a>
            </div>
            <p>If you didn't create an account, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 LLMOptimizer. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """)
        
        # Security alert template
        templates["security_alert"] = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #ffc107; color: #333; padding: 20px; text-align: center; }
        .content { background-color: #f8f9fa; padding: 30px; margin-top: 20px; }
        .alert-box { background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Security Alert</h1>
        </div>
        <div class="content">
            <h2>Hello {{ user_name }},</h2>
            <div class="alert-box">
                <p><strong>Alert Type:</strong> {{ alert_type }}</p>
                <p><strong>Time:</strong> {{ timestamp }}</p>
                {% if details.location %}
                <p><strong>Location:</strong> {{ details.location }}</p>
                {% endif %}
                {% if details.device %}
                <p><strong>Device:</strong> {{ details.device }}</p>
                {% endif %}
                {% if details.ip_address %}
                <p><strong>IP Address:</strong> {{ details.ip_address }}</p>
                {% endif %}
            </div>
            <p>If this activity wasn't you, please secure your account immediately by changing your password and enabling two-factor authentication.</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 LLMOptimizer. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """)
        
        return templates