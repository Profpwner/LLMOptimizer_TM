"""API schemas for auth service."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from uuid import UUID

from ..models.user import UserStatus
from ..models.mfa import MFAMethod


# User schemas
class UserCreate(BaseModel):
    """User registration schema."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    username: str = Field(..., min_length=3, max_length=50)
    phone_number: Optional[str] = None
    accept_terms: bool = Field(..., description="User must accept terms of service")
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric with optional _ or -')
        return v


class UserLogin(BaseModel):
    """User login schema."""
    username: str  # Can be email or username
    password: str
    device_fingerprint: Optional[str] = None
    remember_me: bool = False


class UserUpdate(BaseModel):
    """User profile update schema."""
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    """User response schema."""
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    phone_number: Optional[str]
    is_email_verified: bool
    is_phone_verified: bool
    avatar_url: Optional[str]
    bio: Optional[str]
    timezone: str
    locale: str
    mfa_enabled: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# Token schemas
class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenRefresh(BaseModel):
    """Token refresh request schema."""
    refresh_token: str


# Password schemas
class PasswordReset(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str = Field(..., min_length=8)


class PasswordChange(BaseModel):
    """Password change schema."""
    current_password: str
    new_password: str = Field(..., min_length=8)


# MFA schemas
class MFASetupRequest(BaseModel):
    """MFA setup request schema."""
    method: str  # totp, sms, email
    device_name: Optional[str] = None
    phone_number: Optional[str] = None  # For SMS
    email: Optional[EmailStr] = None  # For email MFA


class MFASetupResponse(BaseModel):
    """MFA setup response schema."""
    setup_id: str
    method: str
    qr_code: Optional[str] = None  # For TOTP
    secret: Optional[str] = None  # For TOTP
    backup_codes: Optional[List[str]] = None
    phone_number: Optional[str] = None  # Masked
    email: Optional[str] = None  # Masked


class MFAVerifyRequest(BaseModel):
    """MFA verification request schema."""
    method: str
    code: str
    setup_id: Optional[str] = None  # For setup verification


class MFAMethodResponse(BaseModel):
    """MFA method response schema."""
    id: str
    method: str
    device_name: Optional[str]
    is_primary: bool
    is_verified: bool
    created_at: datetime
    last_used_at: Optional[datetime]


# OAuth schemas
class OAuthCallbackRequest(BaseModel):
    """OAuth callback request schema."""
    code: str
    state: str


class OAuthConnectionResponse(BaseModel):
    """OAuth connection response schema."""
    provider: str
    connected_at: datetime
    email: Optional[str]
    name: Optional[str]


# Session schemas
class SessionResponse(BaseModel):
    """Session response schema."""
    id: UUID
    device_type: Optional[str]
    device_name: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    ip_address: Optional[str]
    location: Optional[Dict[str, Any]]
    created_at: datetime
    last_activity: Optional[datetime]
    is_current: bool = False


# Admin schemas
class RoleCreate(BaseModel):
    """Role creation schema."""
    name: str
    display_name: str
    description: Optional[str]
    permissions: List[str] = []


class RoleResponse(BaseModel):
    """Role response schema."""
    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    is_system_role: bool
    permissions: List[str]
    user_count: int
    
    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    """User role update schema."""
    user_id: UUID
    role_ids: List[UUID]


# Error schemas
class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    request_id: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response schema."""
    error: str = "Validation Error"
    detail: List[Dict[str, Any]]
    request_id: Optional[str] = None


# Additional schemas needed for auth routes
class Token(BaseModel):
    """Token response for auth endpoints."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    mfa_required: Optional[bool] = False
    mfa_methods: Optional[List[str]] = []


class SAMLCallback(BaseModel):
    """SAML callback schema."""
    SAMLResponse: str
    RelayState: str


class OAuthCallback(BaseModel):
    """OAuth callback schema."""
    code: str
    state: str
    error: Optional[str] = None
    error_description: Optional[str] = None


class RoleAssignment(BaseModel):
    """Role assignment schema."""
    role_id: UUID


class UserListResponse(BaseModel):
    """User list response with pagination."""
    users: List[UserResponse]
    total: int
    page: int
    limit: int
    pages: int


class UserSearch(BaseModel):
    """User search parameters."""
    search: Optional[str] = None
    status: Optional[UserStatus] = None
    role: Optional[str] = None
    verified_only: Optional[bool] = False