"""Base OAuth provider class."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from pydantic import BaseModel, Field
import httpx
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc6749 import OAuth2Token


class OAuthUserInfo(BaseModel):
    """Standardized OAuth user information."""
    provider: str
    provider_user_id: str
    email: Optional[str] = None
    email_verified: bool = False
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture_url: Optional[str] = None
    locale: Optional[str] = None
    raw_data: Dict = Field(default_factory=dict)


class OAuthProvider(ABC):
    """Base class for OAuth providers."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.client = None
        self._setup_client()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @property
    @abstractmethod
    def authorization_endpoint(self) -> str:
        """OAuth authorization endpoint."""
        pass
    
    @property
    @abstractmethod
    def token_endpoint(self) -> str:
        """OAuth token endpoint."""
        pass
    
    @property
    @abstractmethod
    def userinfo_endpoint(self) -> str:
        """User info endpoint."""
        pass
    
    @property
    def scopes(self) -> list[str]:
        """Default scopes to request."""
        return ["openid", "email", "profile"]
    
    def _setup_client(self):
        """Setup OAuth client."""
        oauth = OAuth()
        self.client = oauth.register(
            name=self.name,
            client_id=self.client_id,
            client_secret=self.client_secret,
            server_metadata_url=getattr(self, 'discovery_endpoint', None),
            client_kwargs={
                'scope': ' '.join(self.scopes)
            },
            authorize_url=self.authorization_endpoint,
            access_token_url=self.token_endpoint,
        )
    
    def get_authorization_url(self, state: str, nonce: Optional[str] = None) -> str:
        """Get authorization URL for user redirect."""
        params = {
            'redirect_uri': self.redirect_uri,
            'state': state,
            'scope': ' '.join(self.scopes),
            'response_type': 'code',
            'access_type': 'offline',  # Request refresh token
            'prompt': 'select_account'  # Force account selection
        }
        
        if nonce:
            params['nonce'] = nonce
        
        # Add provider-specific parameters
        params.update(self.get_additional_auth_params())
        
        # Build URL manually for better control
        base_url = self.authorization_endpoint
        query_params = "&".join([f"{k}={v}" for k, v in params.items()])
        query_params += f"&client_id={self.client_id}"
        
        return f"{base_url}?{query_params}"
    
    async def exchange_code_for_token(self, code: str) -> OAuth2Token:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': self.redirect_uri,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
            )
            response.raise_for_status()
            return OAuth2Token(response.json())
    
    async def refresh_access_token(self, refresh_token: str) -> OAuth2Token:
        """Refresh access token using refresh token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
            )
            response.raise_for_status()
            return OAuth2Token(response.json())
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user information from provider."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_endpoint,
                headers={
                    'Authorization': f'Bearer {access_token}'
                }
            )
            response.raise_for_status()
            user_data = response.json()
        
        return self.parse_user_info(user_data)
    
    @abstractmethod
    def parse_user_info(self, data: Dict) -> OAuthUserInfo:
        """Parse provider-specific user data into standardized format."""
        pass
    
    def get_additional_auth_params(self) -> Dict[str, str]:
        """Get additional provider-specific authorization parameters."""
        return {}
    
    async def revoke_token(self, token: str, token_type: str = "access_token") -> bool:
        """Revoke access or refresh token (if supported by provider)."""
        # Default implementation - override in providers that support revocation
        return False