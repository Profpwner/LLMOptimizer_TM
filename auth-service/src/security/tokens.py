"""JWT token management service."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
import secrets

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from ..config import settings


class TokenType(str, Enum):
    """Types of tokens."""
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    MFA = "mfa"
    API_KEY = "api_key"


class TokenData(BaseModel):
    """Token payload data."""
    sub: str  # Subject (user ID or email)
    type: TokenType
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # JWT ID for revocation
    scopes: list[str] = Field(default_factory=list)
    org_id: Optional[str] = None
    session_id: Optional[str] = None
    device_fingerprint: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenService:
    """Service for managing JWT tokens."""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
    def create_token(
        self,
        data: Dict[str, Any],
        token_type: TokenType,
        expires_delta: Optional[timedelta] = None,
        custom_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a JWT token."""
        to_encode = data.copy()
        
        # Set expiration
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = self._get_default_expiration(token_type)
        
        # Add standard claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": token_type.value,
            "jti": secrets.token_urlsafe(16)  # Unique token ID
        })
        
        # Add custom claims
        if custom_claims:
            to_encode.update(custom_claims)
        
        # Encode token
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_access_token(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        org_id: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        device_fingerprint: Optional[str] = None
    ) -> str:
        """Create an access token."""
        data = {
            "sub": user_id,
            "session_id": session_id,
            "org_id": org_id,
            "scopes": scopes or [],
            "device_fingerprint": device_fingerprint
        }
        return self.create_token(
            data,
            TokenType.ACCESS,
            expires_delta=self.access_token_expire
        )
    
    def create_refresh_token(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ) -> str:
        """Create a refresh token."""
        data = {
            "sub": user_id,
            "session_id": session_id,
            "device_fingerprint": device_fingerprint
        }
        return self.create_token(
            data,
            TokenType.REFRESH,
            expires_delta=self.refresh_token_expire
        )
    
    def create_email_verification_token(self, email: str, user_id: str) -> str:
        """Create an email verification token."""
        data = {
            "sub": email,
            "user_id": user_id,
            "purpose": "email_verification"
        }
        return self.create_token(
            data,
            TokenType.EMAIL_VERIFICATION,
            expires_delta=timedelta(days=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_DAYS)
        )
    
    def create_password_reset_token(self, email: str, user_id: str) -> str:
        """Create a password reset token."""
        data = {
            "sub": email,
            "user_id": user_id,
            "purpose": "password_reset"
        }
        return self.create_token(
            data,
            TokenType.PASSWORD_RESET,
            expires_delta=timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        )
    
    def create_mfa_token(self, user_id: str, method: str, valid_minutes: int = 5) -> str:
        """Create a temporary MFA verification token."""
        data = {
            "sub": user_id,
            "mfa_method": method,
            "purpose": "mfa_verification"
        }
        return self.create_token(
            data,
            TokenType.MFA,
            expires_delta=timedelta(minutes=valid_minutes)
        )
    
    def decode_token(self, token: str) -> TokenData:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return TokenData(**payload)
        except JWTError as e:
            raise ValueError(f"Invalid token: {str(e)}")
    
    def verify_token(self, token: str, expected_type: TokenType) -> TokenData:
        """Verify token and check type."""
        token_data = self.decode_token(token)
        
        if token_data.type != expected_type:
            raise ValueError(f"Invalid token type. Expected {expected_type}, got {token_data.type}")
        
        return token_data
    
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        try:
            self.decode_token(token)
            return False
        except ValueError as e:
            return "expired" in str(e).lower()
    
    def get_token_remaining_lifetime(self, token: str) -> Optional[timedelta]:
        """Get remaining lifetime of token."""
        try:
            token_data = self.decode_token(token)
            if token_data.exp:
                remaining = token_data.exp - datetime.utcnow()
                return remaining if remaining.total_seconds() > 0 else timedelta(0)
            return None
        except ValueError:
            return None
    
    def _get_default_expiration(self, token_type: TokenType) -> datetime:
        """Get default expiration for token type."""
        now = datetime.utcnow()
        
        if token_type == TokenType.ACCESS:
            return now + self.access_token_expire
        elif token_type == TokenType.REFRESH:
            return now + self.refresh_token_expire
        elif token_type == TokenType.EMAIL_VERIFICATION:
            return now + timedelta(days=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_DAYS)
        elif token_type == TokenType.PASSWORD_RESET:
            return now + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        elif token_type == TokenType.MFA:
            return now + timedelta(minutes=5)
        else:
            return now + timedelta(hours=1)  # Default 1 hour
    
    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """Generate API key and its hash."""
        # Generate a secure random API key
        api_key = f"llmopt_{secrets.token_urlsafe(32)}"
        
        # Create a hash for storage (in real implementation, use proper hashing)
        import hashlib
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        return api_key, key_hash