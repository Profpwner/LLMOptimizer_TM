"""Configuration settings for the integrations service."""

from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # Service Configuration
    service_name: str = "integrations-service"
    port: int = 8000
    environment: str = "development"
    debug: bool = False
    
    # Security
    secret_key: str
    encryption_key: str
    
    # Database
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "llmoptimizer_integrations"
    postgres_url: Optional[str] = None
    redis_url: str = "redis://localhost:6379"
    
    # Auth Service
    auth_service_url: str = "http://localhost:8001"
    auth_service_api_key: Optional[str] = None
    
    # OAuth Credentials
    # HubSpot
    hubspot_client_id: Optional[str] = None
    hubspot_client_secret: Optional[str] = None
    hubspot_redirect_uri: Optional[str] = None
    
    # Salesforce
    salesforce_client_id: Optional[str] = None
    salesforce_client_secret: Optional[str] = None
    salesforce_redirect_uri: Optional[str] = None
    
    # GitHub
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    github_redirect_uri: Optional[str] = None
    
    # WordPress
    wordpress_api_endpoint: Optional[str] = None
    
    # Webhook Configuration
    webhook_secret: str
    webhook_base_url: str = "http://localhost:8005/api/v1/webhooks"
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_default: int = 100
    rate_limit_window: int = 3600  # 1 hour in seconds
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Integration specific configurations
INTEGRATION_CONFIGS: Dict[str, Dict[str, Any]] = {
    "hubspot": {
        "name": "HubSpot",
        "type": "oauth2",
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "api_base_url": "https://api.hubapi.com",
        "scopes": [
            "crm.objects.contacts.read",
            "crm.objects.contacts.write",
            "crm.objects.companies.read",
            "crm.objects.companies.write",
            "crm.objects.deals.read",
            "crm.objects.deals.write",
        ],
        "rate_limit": {
            "calls": 100,
            "window": 10,  # seconds
        }
    },
    "salesforce": {
        "name": "Salesforce",
        "type": "oauth2",
        "auth_url": "https://login.salesforce.com/services/oauth2/authorize",
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "api_version": "v58.0",
        "scopes": ["api", "refresh_token", "offline_access"],
        "rate_limit": {
            "calls": 5000,
            "window": 3600,  # 1 hour
        }
    },
    "wordpress": {
        "name": "WordPress",
        "type": "api_key",
        "api_version": "wp/v2",
        "rate_limit": {
            "calls": 60,
            "window": 60,  # 1 minute
        }
    },
    "github": {
        "name": "GitHub",
        "type": "oauth2",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "api_base_url": "https://api.github.com",
        "scopes": ["repo", "read:org", "write:org", "webhook"],
        "rate_limit": {
            "calls": 5000,
            "window": 3600,  # 1 hour
        }
    },
}