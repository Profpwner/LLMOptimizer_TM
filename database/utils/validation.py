"""Data validation schemas and utilities for database operations."""

import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator, EmailStr, HttpUrl, constr, conint


# Custom types
TenantID = constr(regex=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
Slug = constr(regex=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', min_length=1, max_length=255)
Username = constr(regex=r'^[a-zA-Z0-9_]+$', min_length=3, max_length=30)
LanguageCode = constr(regex=r'^[a-z]{2}$')


class OrganizationSchema(BaseModel):
    """Validation schema for organization data."""
    
    name: constr(min_length=1, max_length=255)
    slug: Slug
    description: Optional[constr(max_length=1000)] = None
    plan_type: str = Field(..., regex='^(free|starter|professional|enterprise|custom)$')
    
    # Quotas
    max_users: conint(ge=1, le=10000) = 5
    max_content_items: conint(ge=1, le=1000000) = 100
    max_api_calls_per_month: conint(ge=1, le=100000000) = 10000
    storage_quota_gb: float = Field(ge=0.1, le=10000, default=10.0)
    
    # Settings
    settings: Dict[str, Any] = Field(default_factory=dict)
    features: List[str] = Field(default_factory=list)
    
    # Billing
    billing_email: Optional[EmailStr] = None
    
    @validator('slug')
    def validate_slug(cls, v):
        """Ensure slug is unique-friendly."""
        if len(v) < 3:
            raise ValueError('Slug must be at least 3 characters long')
        return v.lower()
    
    @validator('features')
    def validate_features(cls, v):
        """Validate feature flags."""
        allowed_features = {
            'advanced_seo', 'ai_rewrite', 'bulk_operations',
            'custom_models', 'api_access', 'white_label',
            'priority_support', 'dedicated_instance'
        }
        invalid = set(v) - allowed_features
        if invalid:
            raise ValueError(f'Invalid features: {invalid}')
        return v


class UserSchema(BaseModel):
    """Validation schema for user data."""
    
    email: EmailStr
    username: Username
    full_name: Optional[constr(min_length=1, max_length=255)] = None
    password: constr(min_length=8, max_length=128)
    
    # Profile
    avatar_url: Optional[HttpUrl] = None
    bio: Optional[constr(max_length=500)] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('password')
    def validate_password(cls, v):
        """Ensure password meets security requirements."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        """Ensure username is valid."""
        reserved = {'admin', 'root', 'system', 'api', 'test', 'demo'}
        if v.lower() in reserved:
            raise ValueError(f'Username "{v}" is reserved')
        return v


class ContentSchema(BaseModel):
    """Validation schema for content data."""
    
    title: constr(min_length=1, max_length=500)
    slug: Slug
    content_type: str = Field(..., regex='^(article|blog_post|product_description|landing_page|email|social_media|ad_copy|other)$')
    
    # Content data
    content: Optional[constr(min_length=1)] = None
    excerpt: Optional[constr(max_length=500)] = None
    
    # Metadata
    language: LanguageCode = 'en'
    target_keywords: List[constr(min_length=1, max_length=100)] = Field(default_factory=list)
    tags: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    categories: List[constr(min_length=1, max_length=100)] = Field(default_factory=list)
    
    # Settings
    meta_title: Optional[constr(min_length=1, max_length=60)] = None
    meta_description: Optional[constr(min_length=1, max_length=160)] = None
    
    @validator('target_keywords', 'tags', 'categories')
    def validate_list_length(cls, v):
        """Ensure lists don't exceed reasonable limits."""
        if len(v) > 50:
            raise ValueError('List cannot contain more than 50 items')
        return v
    
    @validator('slug')
    def validate_content_slug(cls, v, values):
        """Ensure slug is appropriate for content."""
        if 'title' in values and len(v) > len(values['title']) * 2:
            raise ValueError('Slug is too long compared to title')
        return v


class OptimizationRequestSchema(BaseModel):
    """Validation schema for optimization requests."""
    
    content_id: UUID
    optimization_types: List[str] = Field(..., min_items=1)
    
    # Options
    preserve_tone: bool = True
    target_reading_level: Optional[str] = Field(None, regex='^(elementary|middle|high|college|professional)$')
    focus_keywords: List[constr(min_length=1, max_length=50)] = Field(default_factory=list)
    
    # Constraints
    min_word_count: Optional[conint(ge=50, le=50000)] = None
    max_word_count: Optional[conint(ge=50, le=50000)] = None
    
    @validator('optimization_types')
    def validate_optimization_types(cls, v):
        """Validate optimization types."""
        allowed_types = {
            'seo', 'readability', 'tone', 'keywords',
            'ai_rewrite', 'grammar', 'sentiment'
        }
        invalid = set(v) - allowed_types
        if invalid:
            raise ValueError(f'Invalid optimization types: {invalid}')
        return list(set(v))  # Remove duplicates
    
    @validator('max_word_count')
    def validate_word_count_range(cls, v, values):
        """Ensure max is greater than min."""
        if 'min_word_count' in values and values['min_word_count'] and v:
            if v < values['min_word_count']:
                raise ValueError('max_word_count must be greater than min_word_count')
        return v


class AnalyticsEventSchema(BaseModel):
    """Validation schema for analytics events."""
    
    event_type: constr(min_length=1, max_length=50)
    event_name: constr(min_length=1, max_length=100)
    
    # Associated entities
    user_id: Optional[UUID] = None
    content_id: Optional[UUID] = None
    session_id: Optional[constr(min_length=1, max_length=100)] = None
    
    # Event properties
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Context
    ip_address: Optional[constr(regex=r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}$')] = None
    user_agent: Optional[constr(max_length=500)] = None
    
    # UTM parameters
    utm_source: Optional[constr(max_length=100)] = None
    utm_medium: Optional[constr(max_length=100)] = None
    utm_campaign: Optional[constr(max_length=100)] = None
    utm_term: Optional[constr(max_length=100)] = None
    utm_content: Optional[constr(max_length=100)] = None
    
    @validator('event_type')
    def validate_event_type(cls, v):
        """Validate event type format."""
        if not re.match(r'^[a-z_]+$', v):
            raise ValueError('Event type must be lowercase with underscores')
        return v
    
    @validator('properties')
    def validate_properties(cls, v):
        """Ensure properties don't contain sensitive data."""
        sensitive_keys = {'password', 'credit_card', 'ssn', 'api_key'}
        found = set(k.lower() for k in v.keys()) & sensitive_keys
        if found:
            raise ValueError(f'Properties contain sensitive keys: {found}')
        return v


class APIKeySchema(BaseModel):
    """Validation schema for API key creation."""
    
    name: constr(min_length=1, max_length=255)
    scopes: List[str] = Field(default_factory=list)
    rate_limit_per_hour: conint(ge=1, le=1000000) = 1000
    expires_at: Optional[datetime] = None
    
    @validator('scopes')
    def validate_scopes(cls, v):
        """Validate API scopes."""
        allowed_scopes = {
            'read:content', 'write:content', 'delete:content',
            'read:analytics', 'write:analytics',
            'read:users', 'write:users',
            'admin:all'
        }
        invalid = set(v) - allowed_scopes
        if invalid:
            raise ValueError(f'Invalid scopes: {invalid}')
        return list(set(v))  # Remove duplicates
    
    @validator('expires_at')
    def validate_expiration(cls, v):
        """Ensure expiration is in the future."""
        if v and v <= datetime.utcnow():
            raise ValueError('Expiration date must be in the future')
        return v


class TenantQuotaValidator:
    """Validates operations against tenant quotas."""
    
    @staticmethod
    async def check_content_quota(tenant_id: str, count: int = 1) -> bool:
        """Check if tenant can create more content."""
        from shared.database.manager import db_manager
        from database.schemas.postgresql.models import Organization, Content
        
        # Get organization
        org = await db_manager.postgresql.get(Organization, tenant_id)
        if not org:
            raise ValueError(f"Organization {tenant_id} not found")
        
        # Count existing content
        current_count = await db_manager.postgresql.execute_query(
            "SELECT COUNT(*) as count FROM content WHERE org_id = $1 AND NOT is_deleted",
            {"org_id": tenant_id}
        )
        
        total = current_count[0]["count"] + count
        return total <= org.max_content_items
    
    @staticmethod
    async def check_user_quota(tenant_id: str, count: int = 1) -> bool:
        """Check if tenant can add more users."""
        from shared.database.manager import db_manager
        from database.schemas.postgresql.models import Organization
        
        # Get organization
        org = await db_manager.postgresql.get(Organization, tenant_id)
        if not org:
            raise ValueError(f"Organization {tenant_id} not found")
        
        # Count existing users
        current_count = await db_manager.postgresql.execute_query(
            """
            SELECT COUNT(DISTINCT user_id) as count 
            FROM user_organizations 
            WHERE organization_id = $1
            """,
            {"organization_id": tenant_id}
        )
        
        total = current_count[0]["count"] + count
        return total <= org.max_users
    
    @staticmethod
    async def check_api_quota(tenant_id: str, api_key: str) -> bool:
        """Check if API key has remaining quota."""
        from shared.database.manager import db_manager
        
        # Get current usage from Redis
        current_hour = datetime.utcnow().strftime("%Y%m%d%H")
        usage_key = f"api_usage:{api_key}:{current_hour}"
        
        current_usage = await db_manager.redis.get(usage_key, tenant_id)
        current_usage = int(current_usage) if current_usage else 0
        
        # Get API key rate limit
        api_key_data = await db_manager.postgresql.execute_query(
            "SELECT rate_limit_per_hour FROM api_keys WHERE key_hash = $1",
            {"key_hash": api_key}
        )
        
        if not api_key_data:
            return False
        
        rate_limit = api_key_data[0]["rate_limit_per_hour"]
        return current_usage < rate_limit


class DataSanitizer:
    """Sanitizes data before storage."""
    
    @staticmethod
    def sanitize_html(html: str) -> str:
        """Remove potentially dangerous HTML."""
        # This is a simple example - use a proper HTML sanitizer in production
        dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form']
        clean = html
        
        for tag in dangerous_tags:
            clean = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', clean, flags=re.IGNORECASE | re.DOTALL)
            clean = re.sub(f'<{tag}[^>]*/?>', '', clean, flags=re.IGNORECASE)
        
        # Remove event handlers
        clean = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', clean, flags=re.IGNORECASE)
        
        return clean
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove path traversal attempts
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Keep only safe characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        if ext:
            return f"{name[:200]}.{ext[:10]}"
        return name[:200]
    
    @staticmethod
    def sanitize_json(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Sanitize JSON data to prevent injection attacks."""
        def clean_value(value: Any, depth: int = 0) -> Any:
            if depth > max_depth:
                return None
            
            if isinstance(value, str):
                # Remove null bytes
                return value.replace('\x00', '')
            elif isinstance(value, dict):
                return {k: clean_value(v, depth + 1) for k, v in value.items()}
            elif isinstance(value, list):
                return [clean_value(item, depth + 1) for item in value]
            else:
                return value
        
        return clean_value(data)