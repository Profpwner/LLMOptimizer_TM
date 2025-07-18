"""GitHub OAuth provider implementation."""

from typing import Dict, Optional
import httpx

from .base import OAuthProvider, OAuthUserInfo


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth 2.0 provider."""
    
    @property
    def name(self) -> str:
        return "github"
    
    @property
    def authorization_endpoint(self) -> str:
        return "https://github.com/login/oauth/authorize"
    
    @property
    def token_endpoint(self) -> str:
        return "https://github.com/login/oauth/access_token"
    
    @property
    def userinfo_endpoint(self) -> str:
        return "https://api.github.com/user"
    
    @property
    def scopes(self) -> list[str]:
        return [
            "read:user",
            "user:email"
        ]
    
    async def exchange_code_for_token(self, code: str) -> Dict:
        """Exchange authorization code for access token with GitHub-specific handling."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': self.redirect_uri,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                headers={
                    'Accept': 'application/json'  # GitHub returns form data by default
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Get user information from GitHub."""
        # Get basic user info
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                self.userinfo_endpoint,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            
            # Get user emails (separate endpoint)
            email_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            emails_data = []
            if email_response.status_code == 200:
                emails_data = email_response.json()
        
        # Find primary verified email
        primary_email = user_data.get("email")
        email_verified = False
        
        for email_obj in emails_data:
            if email_obj.get("primary") and email_obj.get("verified"):
                primary_email = email_obj["email"]
                email_verified = True
                break
        
        return self.parse_user_info({
            **user_data,
            "email": primary_email,
            "email_verified": email_verified,
            "emails": emails_data
        })
    
    def parse_user_info(self, data: Dict) -> OAuthUserInfo:
        """Parse GitHub user data."""
        # Split name into given and family names
        full_name = data.get("name", "")
        name_parts = full_name.split(" ", 1) if full_name else []
        given_name = name_parts[0] if name_parts else None
        family_name = name_parts[1] if len(name_parts) > 1 else None
        
        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=str(data.get("id", "")),
            email=data.get("email"),
            email_verified=data.get("email_verified", False),
            name=full_name,
            given_name=given_name,
            family_name=family_name,
            picture_url=data.get("avatar_url"),
            locale=None,  # GitHub doesn't provide locale
            raw_data=data
        )
    
    def get_additional_auth_params(self) -> Dict[str, str]:
        """Get GitHub-specific auth parameters."""
        return {
            "allow_signup": "true"  # Allow users to sign up during OAuth
        }
    
    async def get_user_organizations(self, access_token: str) -> list[Dict]:
        """Get user's organizations."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/user/orgs",
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Accept': 'application/vnd.github.v3+json'
                    }
                )
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return []
    
    async def check_org_membership(self, access_token: str, org: str) -> bool:
        """Check if user is member of specific organization."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.github.com/user/memberships/orgs/{org}",
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Accept': 'application/vnd.github.v3+json'
                    }
                )
                return response.status_code == 200
        except Exception:
            pass
        return False