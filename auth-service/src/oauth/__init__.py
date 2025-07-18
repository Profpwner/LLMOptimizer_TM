"""OAuth 2.0 providers for social login."""

from .base import OAuthProvider, OAuthUserInfo
from .google import GoogleOAuthProvider
from .microsoft import MicrosoftOAuthProvider
from .github import GitHubOAuthProvider
from .manager import OAuthManager

__all__ = [
    "OAuthProvider",
    "OAuthUserInfo",
    "GoogleOAuthProvider",
    "MicrosoftOAuthProvider",
    "GitHubOAuthProvider",
    "OAuthManager",
]