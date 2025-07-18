"""Base integration class and utilities."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, AsyncIterator
from datetime import datetime, timedelta
import asyncio
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from app.models import Integration, OAuthToken, SyncJob, SyncLog
from app.core.config import get_settings
from app.utils.crypto import encrypt_token, decrypt_token
from app.utils.rate_limiter import RateLimiter


logger = logging.getLogger(__name__)
settings = get_settings()


class IntegrationError(Exception):
    """Base integration error."""
    pass


class AuthenticationError(IntegrationError):
    """Authentication failed."""
    pass


class RateLimitError(IntegrationError):
    """Rate limit exceeded."""
    pass


class WebhookVerificationError(IntegrationError):
    """Webhook signature verification failed."""
    pass


class BaseIntegration(ABC):
    """Base class for all integrations."""
    
    def __init__(self, integration: Integration):
        self.integration = integration
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.rate_limiter = RateLimiter(
            redis_url=settings.redis_url,
            prefix=f"integration:{integration.integration_type}:{integration.id}"
        )
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
    
    # Abstract methods that must be implemented
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the integration connection is valid."""
        pass
    
    @abstractmethod
    async def sync_data(self, job: SyncJob) -> Dict[str, Any]:
        """Perform data synchronization."""
        pass
    
    @abstractmethod
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle incoming webhook."""
        pass
    
    @abstractmethod
    def verify_webhook_signature(self, signature: str, payload: bytes) -> bool:
        """Verify webhook signature."""
        pass
    
    # OAuth flow methods (override for OAuth integrations)
    
    async def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL."""
        raise NotImplementedError("This integration does not support OAuth")
    
    async def exchange_code_for_token(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        raise NotImplementedError("This integration does not support OAuth")
    
    async def refresh_access_token(self) -> OAuthToken:
        """Refresh OAuth access token."""
        raise NotImplementedError("This integration does not support OAuth")
    
    # Common utility methods
    
    async def ensure_authenticated(self) -> None:
        """Ensure the integration is authenticated, refresh token if needed."""
        if self.integration.oauth_token:
            if self.integration.oauth_token.expires_at:
                if datetime.utcnow() >= self.integration.oauth_token.expires_at - timedelta(minutes=5):
                    # Token is expired or about to expire, refresh it
                    await self.refresh_and_save_token()
    
    async def refresh_and_save_token(self) -> None:
        """Refresh token and save to database."""
        try:
            new_token = await self.refresh_access_token()
            self.integration.oauth_token = new_token
            # Save to database (implementation depends on your database layer)
            await self.save_integration()
        except Exception as e:
            logger.error(f"Failed to refresh token for integration {self.integration.id}: {e}")
            raise AuthenticationError(f"Token refresh failed: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(httpx.TimeoutException)
    )
    async def make_api_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make API request with rate limiting and retries."""
        # Check rate limit
        rate_limit_key = f"{method}:{url}"
        if not await self.rate_limiter.check_rate_limit(rate_limit_key):
            raise RateLimitError(f"Rate limit exceeded for {rate_limit_key}")
        
        # Ensure authenticated
        await self.ensure_authenticated()
        
        # Prepare headers
        request_headers = headers or {}
        if self.integration.oauth_token:
            token = decrypt_token(
                self.integration.oauth_token.access_token,
                settings.encryption_key
            ) if self.integration.oauth_token.encrypted else self.integration.oauth_token.access_token
            request_headers["Authorization"] = f"{self.integration.oauth_token.token_type} {token}"
        elif self.integration.api_key:
            # API key authentication (implementation varies by service)
            request_headers["X-API-Key"] = self.integration.api_key
        
        # Make request
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=request_headers,
                params=params,
                json=json,
                data=data,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError(f"Rate limit exceeded: {e}")
            elif e.response.status_code == 401:
                raise AuthenticationError(f"Authentication failed: {e}")
            else:
                raise IntegrationError(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise IntegrationError(f"API request failed: {str(e)}")
    
    async def paginate_api_results(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        max_pages: Optional[int] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Paginate through API results."""
        page = 1
        total_pages = 0
        
        while True:
            # Add pagination parameters
            request_params = params or {}
            request_params.update({
                "page": page,
                "limit": page_size,
            })
            
            # Make request
            response = await self.make_api_request(method, url, params=request_params)
            data = response.json()
            
            # Yield results
            results = self.extract_results_from_response(data)
            for result in results:
                yield result
            
            # Check if more pages
            if not self.has_more_pages(data, page):
                break
            
            page += 1
            total_pages += 1
            
            if max_pages and total_pages >= max_pages:
                break
            
            # Small delay between pages
            await asyncio.sleep(0.1)
    
    def extract_results_from_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract results from paginated response (override if needed)."""
        if isinstance(data, list):
            return data
        elif "results" in data:
            return data["results"]
        elif "data" in data:
            return data["data"]
        else:
            return []
    
    def has_more_pages(self, data: Dict[str, Any], current_page: int) -> bool:
        """Check if there are more pages (override if needed)."""
        if isinstance(data, dict):
            if "has_more" in data:
                return data["has_more"]
            elif "next" in data:
                return data["next"] is not None
            elif "total_pages" in data:
                return current_page < data["total_pages"]
        return False
    
    async def save_integration(self) -> None:
        """Save integration to database (implement in service layer)."""
        # This would be implemented in the service layer
        pass
    
    async def log_sync_operation(
        self,
        sync_job_id: str,
        level: str,
        operation: str,
        entity_type: str,
        message: str,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log sync operation."""
        log = SyncLog(
            sync_job_id=sync_job_id,
            integration_id=self.integration.id,
            level=level,
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message,
            details=details or {},
            error=error,
        )
        # Save log to database (implement in service layer)
        logger.info(f"Sync log: {log.dict()}")