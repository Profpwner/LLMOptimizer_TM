"""Microsoft/Azure AD OAuth provider implementation."""

from typing import Dict, Optional
import httpx

from .base import OAuthProvider, OAuthUserInfo


class MicrosoftOAuthProvider(OAuthProvider):
    """Microsoft/Azure AD OAuth 2.0 provider."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, tenant: str = "common"):
        self.tenant = tenant  # common, organizations, consumers, or specific tenant ID
        super().__init__(client_id, client_secret, redirect_uri)
    
    @property
    def name(self) -> str:
        return "microsoft"
    
    @property
    def discovery_endpoint(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/v2.0/.well-known/openid-configuration"
    
    @property
    def authorization_endpoint(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/authorize"
    
    @property
    def token_endpoint(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
    
    @property
    def userinfo_endpoint(self) -> str:
        return "https://graph.microsoft.com/v1.0/me"
    
    @property
    def scopes(self) -> list[str]:
        return [
            "openid",
            "email",
            "profile",
            "User.Read",
            "offline_access"  # For refresh token
        ]
    
    def parse_user_info(self, data: Dict) -> OAuthUserInfo:
        """Parse Microsoft user data."""
        # Microsoft Graph API returns different field names
        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=data.get("id", ""),
            email=data.get("mail") or data.get("userPrincipalName"),
            email_verified=True,  # Microsoft verifies emails
            name=data.get("displayName"),
            given_name=data.get("givenName"),
            family_name=data.get("surname"),
            picture_url=None,  # Requires additional API call
            locale=data.get("preferredLanguage"),
            raw_data=data
        )
    
    def get_additional_auth_params(self) -> Dict[str, str]:
        """Get Microsoft-specific auth parameters."""
        return {
            "response_mode": "query",
            "domain_hint": "organizations"  # Hint for work/school accounts
        }
    
    async def get_user_photo(self, access_token: str) -> Optional[bytes]:
        """Get user's profile photo."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/photo/$value",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code == 200:
                    return response.content
        except Exception:
            pass
        return None
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Enhanced user info with additional fields."""
        # Get basic user info
        user_info = await super().get_user_info(access_token)
        
        # Try to get profile photo URL
        try:
            async with httpx.AsyncClient() as client:
                # Check if photo exists
                photo_response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/photo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if photo_response.status_code == 200:
                    # Photo exists, construct URL (note: this requires app permissions)
                    user_info.picture_url = f"https://graph.microsoft.com/v1.0/me/photo/$value"
        except Exception:
            pass
        
        return user_info
    
    async def get_user_organizations(self, access_token: str) -> list[Dict]:
        """Get user's organizations (requires additional permissions)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/memberOf",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("value", [])
        except Exception:
            pass
        return []