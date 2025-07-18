"""OAuth provider manager."""

from typing import Dict, Optional
import secrets
import base64
import json
from datetime import datetime, timedelta

from ..config import settings
from .base import OAuthProvider
from .google import GoogleOAuthProvider
from .microsoft import MicrosoftOAuthProvider
from .github import GitHubOAuthProvider


class OAuthManager:
    """Manages OAuth providers and state."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.providers: Dict[str, OAuthProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize configured OAuth providers."""
        # Google OAuth
        if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
            self.providers["google"] = GoogleOAuthProvider(
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                redirect_uri=settings.GOOGLE_REDIRECT_URI or f"{settings.FRONTEND_URL}/auth/callback/google"
            )
        
        # Microsoft OAuth
        if settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET:
            self.providers["microsoft"] = MicrosoftOAuthProvider(
                client_id=settings.MICROSOFT_CLIENT_ID,
                client_secret=settings.MICROSOFT_CLIENT_SECRET,
                redirect_uri=settings.MICROSOFT_REDIRECT_URI or f"{settings.FRONTEND_URL}/auth/callback/microsoft"
            )
        
        # GitHub OAuth
        if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
            self.providers["github"] = GitHubOAuthProvider(
                client_id=settings.GITHUB_CLIENT_ID,
                client_secret=settings.GITHUB_CLIENT_SECRET,
                redirect_uri=settings.GITHUB_REDIRECT_URI or f"{settings.FRONTEND_URL}/auth/callback/github"
            )
    
    def get_provider(self, provider_name: str) -> Optional[OAuthProvider]:
        """Get OAuth provider by name."""
        return self.providers.get(provider_name.lower())
    
    def list_providers(self) -> list[str]:
        """List available OAuth providers."""
        return list(self.providers.keys())
    
    async def create_authorization_url(
        self,
        provider_name: str,
        user_ip: str,
        user_agent: str,
        additional_state: Optional[Dict] = None
    ) -> tuple[str, str]:
        """Create authorization URL with secure state."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        # Generate secure state
        state_data = {
            "provider": provider_name,
            "timestamp": datetime.utcnow().isoformat(),
            "ip": user_ip,
            "user_agent": user_agent,
            "nonce": secrets.token_urlsafe(16)
        }
        
        if additional_state:
            state_data.update(additional_state)
        
        # Encode state
        state_json = json.dumps(state_data)
        state = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        # Store state in Redis or memory
        await self._store_state(state, state_data)
        
        # Generate authorization URL
        auth_url = provider.get_authorization_url(state)
        
        return auth_url, state
    
    async def validate_callback(
        self,
        provider_name: str,
        state: str,
        code: str,
        user_ip: str
    ) -> Dict:
        """Validate OAuth callback and exchange code for token."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        # Validate state
        state_data = await self._get_state(state)
        if not state_data:
            raise ValueError("Invalid or expired state")
        
        # Check state data
        if state_data.get("provider") != provider_name:
            raise ValueError("Provider mismatch")
        
        # Check timestamp (allow 10 minutes)
        state_timestamp = datetime.fromisoformat(state_data["timestamp"])
        if datetime.utcnow() - state_timestamp > timedelta(minutes=10):
            raise ValueError("State expired")
        
        # Optionally validate IP
        if state_data.get("ip") != user_ip:
            # Log potential security issue but don't block (user might be on mobile)
            pass
        
        # Exchange code for token
        token_data = await provider.exchange_code_for_token(code)
        
        # Get user info
        user_info = await provider.get_user_info(token_data["access_token"])
        
        # Delete used state
        await self._delete_state(state)
        
        return {
            "provider": provider_name,
            "token_data": token_data,
            "user_info": user_info,
            "state_data": state_data
        }
    
    async def refresh_token(self, provider_name: str, refresh_token: str) -> Dict:
        """Refresh OAuth access token."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        return await provider.refresh_access_token(refresh_token)
    
    async def revoke_token(self, provider_name: str, token: str) -> bool:
        """Revoke OAuth token."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")
        
        return await provider.revoke_token(token)
    
    async def _store_state(self, state: str, data: Dict):
        """Store OAuth state data."""
        if self.redis_client:
            await self.redis_client.setex(
                f"oauth_state:{state}",
                600,  # 10 minutes
                json.dumps(data)
            )
        else:
            # In-memory fallback (not recommended for production)
            if not hasattr(self, '_state_store'):
                self._state_store = {}
            self._state_store[state] = {
                "data": data,
                "expires": datetime.utcnow() + timedelta(minutes=10)
            }
    
    async def _get_state(self, state: str) -> Optional[Dict]:
        """Get OAuth state data."""
        if self.redis_client:
            data = await self.redis_client.get(f"oauth_state:{state}")
            return json.loads(data) if data else None
        else:
            # In-memory fallback
            if hasattr(self, '_state_store') and state in self._state_store:
                stored = self._state_store[state]
                if stored["expires"] > datetime.utcnow():
                    return stored["data"]
                else:
                    del self._state_store[state]
            return None
    
    async def _delete_state(self, state: str):
        """Delete OAuth state data."""
        if self.redis_client:
            await self.redis_client.delete(f"oauth_state:{state}")
        elif hasattr(self, '_state_store') and state in self._state_store:
            del self._state_store[state]