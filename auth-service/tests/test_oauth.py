"""Tests for OAuth 2.0 functionality."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import json
from urllib.parse import urlparse, parse_qs

from src.oauth.oauth_manager import OAuthManager
from src.oauth.providers import GoogleOAuthProvider, GitHubOAuthProvider, MicrosoftOAuthProvider
from src.models.user import User, UserStatus
from src.models.oauth import OAuthAccount


class TestOAuthProviders:
    """Test OAuth provider implementations."""
    
    @pytest.mark.asyncio
    async def test_google_provider_initialization(self):
        """Test Google OAuth provider initialization."""
        provider = GoogleOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback"
        )
        
        assert provider.name == "google"
        assert provider.client_id == "test-client-id"
        assert provider.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth"
        assert provider.token_url == "https://oauth2.googleapis.com/token"
    
    @pytest.mark.asyncio
    async def test_github_provider_initialization(self):
        """Test GitHub OAuth provider initialization."""
        provider = GitHubOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback"
        )
        
        assert provider.name == "github"
        assert provider.authorize_url == "https://github.com/login/oauth/authorize"
        assert provider.token_url == "https://github.com/login/oauth/access_token"
    
    @pytest.mark.asyncio
    async def test_microsoft_provider_initialization(self):
        """Test Microsoft OAuth provider initialization."""
        provider = MicrosoftOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback"
        )
        
        assert provider.name == "microsoft"
        assert "login.microsoftonline.com" in provider.authorize_url
        assert "login.microsoftonline.com" in provider.token_url
    
    def test_authorization_url_generation(self):
        """Test OAuth authorization URL generation."""
        provider = GoogleOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback"
        )
        
        state = "test-state-123"
        auth_url = provider.get_authorization_url(state)
        
        parsed_url = urlparse(auth_url)
        query_params = parse_qs(parsed_url.query)
        
        assert parsed_url.scheme == "https"
        assert parsed_url.netloc == "accounts.google.com"
        assert query_params["client_id"][0] == "test-client-id"
        assert query_params["redirect_uri"][0] == "http://localhost:8000/callback"
        assert query_params["state"][0] == state
        assert query_params["response_type"][0] == "code"
        assert "scope" in query_params
    
    @pytest.mark.asyncio
    async def test_token_exchange(self):
        """Test OAuth code to token exchange."""
        provider = GoogleOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback"
        )
        
        mock_response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test-refresh-token",
            "scope": "email profile"
        }
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response
            )
            
            tokens = await provider.exchange_code_for_token("test-code")
            
            assert tokens["access_token"] == "test-access-token"
            assert tokens["refresh_token"] == "test-refresh-token"
            assert "expires_in" in tokens
    
    @pytest.mark.asyncio
    async def test_user_info_retrieval(self):
        """Test retrieving user info from OAuth provider."""
        provider = GoogleOAuthProvider(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/callback"
        )
        
        mock_user_info = {
            "id": "google-user-123",
            "email": "user@example.com",
            "verified_email": True,
            "name": "Test User",
            "picture": "https://example.com/picture.jpg"
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_user_info
            )
            
            user_info = await provider.get_user_info("test-access-token")
            
            assert user_info["id"] == "google-user-123"
            assert user_info["email"] == "user@example.com"
            assert user_info["name"] == "Test User"


class TestOAuthManager:
    """Test OAuth manager functionality."""
    
    @pytest.fixture
    def oauth_manager(self, db, redis_client):
        """Create OAuth manager instance."""
        manager = OAuthManager(db, redis_client)
        manager.providers = {
            "google": GoogleOAuthProvider(
                client_id="test-google-id",
                client_secret="test-google-secret",
                redirect_uri="http://localhost:8000/auth/oauth/google/callback"
            ),
            "github": GitHubOAuthProvider(
                client_id="test-github-id",
                client_secret="test-github-secret",
                redirect_uri="http://localhost:8000/auth/oauth/github/callback"
            )
        }
        return manager
    
    @pytest.mark.asyncio
    async def test_initiate_oauth_flow(self, oauth_manager: OAuthManager):
        """Test initiating OAuth flow."""
        provider_name = "google"
        auth_url, state = await oauth_manager.initiate_oauth_flow(provider_name)
        
        assert auth_url is not None
        assert state is not None
        assert len(state) >= 32  # Secure random state
        
        # Verify state is stored in Redis
        stored_state = await oauth_manager.redis.get(f"oauth_state:{state}")
        assert stored_state == provider_name
    
    @pytest.mark.asyncio
    async def test_handle_oauth_callback_new_user(
        self,
        oauth_manager: OAuthManager,
        db
    ):
        """Test OAuth callback for new user registration."""
        provider_name = "google"
        state = "test-state-123"
        code = "test-auth-code"
        
        # Store state in Redis
        await oauth_manager.redis.setex(
            f"oauth_state:{state}",
            300,
            provider_name
        )
        
        # Mock OAuth provider responses
        mock_tokens = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600
        }
        
        mock_user_info = {
            "id": "google-123",
            "email": "newuser@example.com",
            "name": "New User",
            "picture": "https://example.com/picture.jpg"
        }
        
        with patch.object(
            oauth_manager.providers[provider_name],
            "exchange_code_for_token",
            return_value=mock_tokens
        ):
            with patch.object(
                oauth_manager.providers[provider_name],
                "get_user_info",
                return_value=mock_user_info
            ):
                user, tokens = await oauth_manager.handle_oauth_callback(
                    provider_name,
                    code,
                    state
                )
        
        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is True
        
        # Check OAuth account was created
        oauth_account = await db.query(OAuthAccount).filter(
            OAuthAccount.provider == provider_name,
            OAuthAccount.provider_user_id == "google-123"
        ).first()
        
        assert oauth_account is not None
        assert oauth_account.user_id == user.id
        assert oauth_account.email == "newuser@example.com"
    
    @pytest.mark.asyncio
    async def test_handle_oauth_callback_existing_user(
        self,
        oauth_manager: OAuthManager,
        test_user: User,
        db
    ):
        """Test OAuth callback for existing user login."""
        provider_name = "google"
        state = "test-state-123"
        code = "test-auth-code"
        
        # Create existing OAuth account
        oauth_account = OAuthAccount(
            user_id=test_user.id,
            provider=provider_name,
            provider_user_id="google-123",
            email=test_user.email
        )
        db.add(oauth_account)
        await db.commit()
        
        # Store state in Redis
        await oauth_manager.redis.setex(
            f"oauth_state:{state}",
            300,
            provider_name
        )
        
        # Mock OAuth provider responses
        mock_tokens = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600
        }
        
        mock_user_info = {
            "id": "google-123",
            "email": test_user.email,
            "name": test_user.full_name
        }
        
        with patch.object(
            oauth_manager.providers[provider_name],
            "exchange_code_for_token",
            return_value=mock_tokens
        ):
            with patch.object(
                oauth_manager.providers[provider_name],
                "get_user_info",
                return_value=mock_user_info
            ):
                user, tokens = await oauth_manager.handle_oauth_callback(
                    provider_name,
                    code,
                    state
                )
        
        assert user.id == test_user.id
        assert tokens["access_token"] == "test-access-token"
    
    @pytest.mark.asyncio
    async def test_handle_oauth_callback_invalid_state(
        self,
        oauth_manager: OAuthManager
    ):
        """Test OAuth callback with invalid state."""
        provider_name = "google"
        state = "invalid-state"
        code = "test-auth-code"
        
        with pytest.raises(ValueError, match="Invalid OAuth state"):
            await oauth_manager.handle_oauth_callback(
                provider_name,
                code,
                state
            )
    
    @pytest.mark.asyncio
    async def test_link_oauth_account(
        self,
        oauth_manager: OAuthManager,
        test_user: User,
        db
    ):
        """Test linking OAuth account to existing user."""
        provider_name = "github"
        provider_user_id = "github-456"
        
        await oauth_manager.link_oauth_account(
            test_user,
            provider_name,
            provider_user_id,
            email="user@github.com",
            metadata={"login": "testuser"}
        )
        
        # Check OAuth account was created
        oauth_account = await db.query(OAuthAccount).filter(
            OAuthAccount.user_id == test_user.id,
            OAuthAccount.provider == provider_name
        ).first()
        
        assert oauth_account is not None
        assert oauth_account.provider_user_id == provider_user_id
        assert oauth_account.email == "user@github.com"
        assert oauth_account.metadata["login"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_unlink_oauth_account(
        self,
        oauth_manager: OAuthManager,
        test_user: User,
        db
    ):
        """Test unlinking OAuth account."""
        provider_name = "google"
        
        # Create OAuth account
        oauth_account = OAuthAccount(
            user_id=test_user.id,
            provider=provider_name,
            provider_user_id="google-123",
            email=test_user.email
        )
        db.add(oauth_account)
        await db.commit()
        
        # Unlink account
        await oauth_manager.unlink_oauth_account(test_user, provider_name)
        
        # Check account was removed
        account = await db.query(OAuthAccount).filter(
            OAuthAccount.user_id == test_user.id,
            OAuthAccount.provider == provider_name
        ).first()
        
        assert account is None


class TestOAuthIntegration:
    """Integration tests for OAuth functionality."""
    
    @pytest.mark.asyncio
    async def test_oauth_login_flow(self, test_client, redis_client):
        """Test complete OAuth login flow."""
        # Initiate OAuth flow
        response = test_client.get("/api/v1/auth/oauth/google/authorize")
        assert response.status_code == 307  # Redirect
        
        location = response.headers["location"]
        parsed_url = urlparse(location)
        query_params = parse_qs(parsed_url.query)
        
        assert "state" in query_params
        state = query_params["state"][0]
        
        # Verify state is stored
        stored_provider = await redis_client.get(f"oauth_state:{state}")
        assert stored_provider == "google"
    
    @pytest.mark.asyncio
    async def test_oauth_callback_success(
        self,
        test_client,
        redis_client,
        db
    ):
        """Test successful OAuth callback."""
        state = "test-state-123"
        code = "test-auth-code"
        
        # Store state
        await redis_client.setex(f"oauth_state:{state}", 300, "google")
        
        # Mock OAuth provider
        with patch("src.oauth.oauth_manager.GoogleOAuthProvider") as MockProvider:
            mock_provider = MockProvider.return_value
            mock_provider.exchange_code_for_token = AsyncMock(return_value={
                "access_token": "test-token",
                "refresh_token": "refresh-token"
            })
            mock_provider.get_user_info = AsyncMock(return_value={
                "id": "google-123",
                "email": "oauth@example.com",
                "name": "OAuth User"
            })
            
            response = test_client.get(
                f"/api/v1/auth/oauth/google/callback?code={code}&state={state}"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_oauth_account_listing(
        self,
        test_client,
        test_user: User,
        auth_headers: dict,
        db
    ):
        """Test listing linked OAuth accounts."""
        # Create OAuth accounts
        accounts = [
            OAuthAccount(
                user_id=test_user.id,
                provider="google",
                provider_user_id="google-123",
                email="user@gmail.com"
            ),
            OAuthAccount(
                user_id=test_user.id,
                provider="github",
                provider_user_id="github-456",
                email="user@github.com"
            )
        ]
        db.add_all(accounts)
        await db.commit()
        
        # List accounts
        response = test_client.get(
            "/api/v1/users/me/oauth-accounts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        providers = [account["provider"] for account in data]
        assert "google" in providers
        assert "github" in providers