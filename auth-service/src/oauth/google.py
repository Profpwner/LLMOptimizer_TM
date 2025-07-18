"""Google OAuth provider implementation."""

from typing import Dict, Optional
import httpx

from .base import OAuthProvider, OAuthUserInfo


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth 2.0 provider."""
    
    @property
    def name(self) -> str:
        return "google"
    
    @property
    def discovery_endpoint(self) -> str:
        return "https://accounts.google.com/.well-known/openid-configuration"
    
    @property
    def authorization_endpoint(self) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth"
    
    @property
    def token_endpoint(self) -> str:
        return "https://oauth2.googleapis.com/token"
    
    @property
    def userinfo_endpoint(self) -> str:
        return "https://openidconnect.googleapis.com/v1/userinfo"
    
    @property
    def revocation_endpoint(self) -> str:
        return "https://oauth2.googleapis.com/revoke"
    
    @property
    def scopes(self) -> list[str]:
        return [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/user.phonenumbers.read"  # Optional
        ]
    
    def parse_user_info(self, data: Dict) -> OAuthUserInfo:
        """Parse Google user data."""
        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=data.get("sub", ""),
            email=data.get("email"),
            email_verified=data.get("email_verified", False),
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture_url=data.get("picture"),
            locale=data.get("locale"),
            raw_data=data
        )
    
    def get_additional_auth_params(self) -> Dict[str, str]:
        """Get Google-specific auth parameters."""
        return {
            "include_granted_scopes": "true",  # Incremental authorization
            "access_type": "offline",  # Get refresh token
            "prompt": "select_account"  # Force account selection
        }
    
    async def revoke_token(self, token: str, token_type: str = "access_token") -> bool:
        """Revoke Google OAuth token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.revocation_endpoint,
                params={"token": token}
            )
            return response.status_code == 200
    
    async def get_user_phone(self, access_token: str) -> Optional[str]:
        """Get user's phone number if available and permitted."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://people.googleapis.com/v1/people/me?personFields=phoneNumbers",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    phone_numbers = data.get("phoneNumbers", [])
                    if phone_numbers:
                        return phone_numbers[0].get("value")
        except Exception:
            pass
        return None