"""Configuration settings for the auth service."""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    SERVICE_NAME: str = "auth-service"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # Security
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24
    EMAIL_VERIFICATION_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGITS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    PASSWORD_HISTORY_COUNT: int = 5
    
    # Account Security
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = 30
    SUSPICIOUS_LOGIN_THRESHOLD: int = 3
    
    # Session Management
    SESSION_LIFETIME_HOURS: int = 24
    SESSION_IDLE_TIMEOUT_MINUTES: int = 60
    MAX_SESSIONS_PER_USER: int = 5
    
    # Database
    POSTGRES_URL: str = Field(..., env="POSTGRES_URL")
    MONGODB_URL: str = Field(default="mongodb://mongodb:27017", env="MONGODB_URL")
    REDIS_URL: str = Field(default="redis://redis:6379", env="REDIS_URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # OAuth 2.0
    GOOGLE_CLIENT_ID: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(None, env="GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: Optional[str] = Field(None, env="GOOGLE_REDIRECT_URI")
    
    MICROSOFT_CLIENT_ID: Optional[str] = Field(None, env="MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET: Optional[str] = Field(None, env="MICROSOFT_CLIENT_SECRET")
    MICROSOFT_REDIRECT_URI: Optional[str] = Field(None, env="MICROSOFT_REDIRECT_URI")
    
    GITHUB_CLIENT_ID: Optional[str] = Field(None, env="GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = Field(None, env="GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: Optional[str] = Field(None, env="GITHUB_REDIRECT_URI")
    
    # SAML 2.0
    SAML_SP_ENTITY_ID: Optional[str] = Field(None, env="SAML_SP_ENTITY_ID")
    SAML_SP_ACS_URL: Optional[str] = Field(None, env="SAML_SP_ACS_URL")
    SAML_SP_X509_CERT: Optional[str] = Field(None, env="SAML_SP_X509_CERT")
    SAML_SP_PRIVATE_KEY: Optional[str] = Field(None, env="SAML_SP_PRIVATE_KEY")
    SAML_PROVIDERS: dict = Field(default_factory=dict, env="SAML_PROVIDERS")
    
    # Email
    SMTP_HOST: Optional[str] = Field(None, env="SMTP_HOST")
    SMTP_PORT: int = Field(587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(True, env="SMTP_USE_TLS")
    EMAIL_FROM: str = Field("noreply@llmoptimizer.com", env="EMAIL_FROM")
    EMAIL_FROM_NAME: str = Field("LLMOptimizer", env="EMAIL_FROM_NAME")
    
    # Twilio (SMS)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(None, env="TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER: Optional[str] = Field(None, env="TWILIO_FROM_NUMBER")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Frontend URLs
    FRONTEND_URL: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    API_URL: str = Field(default="http://localhost:8000", env="API_URL")
    PASSWORD_RESET_URL: str = Field(
        default="http://localhost:3000/auth/reset-password",
        env="PASSWORD_RESET_URL"
    )
    EMAIL_VERIFICATION_URL: str = Field(
        default="http://localhost:3000/auth/verify-email",
        env="EMAIL_VERIFICATION_URL"
    )
    
    # Feature Flags
    ENABLE_OAUTH: bool = Field(default=True, env="ENABLE_OAUTH")
    ENABLE_SAML: bool = Field(default=True, env="ENABLE_SAML")
    ENABLE_MFA: bool = Field(default=True, env="ENABLE_MFA")
    ENABLE_SMS_MFA: bool = Field(default=True, env="ENABLE_SMS_MFA")
    ENABLE_EMAIL_VERIFICATION: bool = Field(default=True, env="ENABLE_EMAIL_VERIFICATION")
    ENABLE_DEVICE_TRACKING: bool = Field(default=True, env="ENABLE_DEVICE_TRACKING")
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()