"""HubSpot integration implementation."""

import hmac
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import urllib.parse
import logging

from app.integrations.base import BaseIntegration, IntegrationError, AuthenticationError
from app.integrations.registry import IntegrationRegistry
from app.models import IntegrationType, OAuthToken, SyncJob
from app.core.config import get_settings, INTEGRATION_CONFIGS
from app.utils.crypto import encrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()


@IntegrationRegistry.register(IntegrationType.HUBSPOT)
class HubSpotIntegration(BaseIntegration):
    """HubSpot CRM integration."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = INTEGRATION_CONFIGS["hubspot"]
        self.api_base_url = self.config["api_base_url"]
    
    async def get_authorization_url(self, state: str) -> str:
        """Generate HubSpot OAuth authorization URL."""
        params = {
            "client_id": settings.hubspot_client_id,
            "redirect_uri": settings.hubspot_redirect_uri,
            "scope": " ".join(self.config["scopes"]),
            "state": state,
        }
        return f"{self.config['auth_url']}?{urllib.parse.urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.hubspot_client_id,
            "client_secret": settings.hubspot_client_secret,
            "redirect_uri": settings.hubspot_redirect_uri,
            "code": code,
        }
        
        response = await self.http_client.post(
            self.config["token_url"],
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        if response.status_code != 200:
            raise AuthenticationError(f"Token exchange failed: {response.text}")
        
        token_data = response.json()
        
        # Calculate expiration time
        expires_at = None
        if "expires_in" in token_data:
            expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        return OAuthToken(
            access_token=encrypt_token(token_data["access_token"], settings.encryption_key),
            refresh_token=encrypt_token(token_data["refresh_token"], settings.encryption_key),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
            encrypted=True,
        )
    
    async def refresh_access_token(self) -> OAuthToken:
        """Refresh HubSpot access token."""
        if not self.integration.oauth_token or not self.integration.oauth_token.refresh_token:
            raise AuthenticationError("No refresh token available")
        
        refresh_token = self.integration.oauth_token.refresh_token
        if self.integration.oauth_token.encrypted:
            from app.utils.crypto import decrypt_token
            refresh_token = decrypt_token(refresh_token, settings.encryption_key)
        
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.hubspot_client_id,
            "client_secret": settings.hubspot_client_secret,
            "refresh_token": refresh_token,
        }
        
        response = await self.http_client.post(
            self.config["token_url"],
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        if response.status_code != 200:
            raise AuthenticationError(f"Token refresh failed: {response.text}")
        
        token_data = response.json()
        
        # Calculate expiration time
        expires_at = None
        if "expires_in" in token_data:
            expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        return OAuthToken(
            access_token=encrypt_token(token_data["access_token"], settings.encryption_key),
            refresh_token=encrypt_token(token_data["refresh_token"], settings.encryption_key),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
            encrypted=True,
        )
    
    async def test_connection(self) -> bool:
        """Test HubSpot connection."""
        try:
            response = await self.make_api_request(
                "GET",
                f"{self.api_base_url}/account-info/v3/details"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def sync_data(self, job: SyncJob) -> Dict[str, Any]:
        """Sync data with HubSpot."""
        results = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "entity_results": {}
        }
        
        for entity_type in job.entity_types:
            try:
                if entity_type == "contacts":
                    entity_results = await self._sync_contacts(job)
                elif entity_type == "companies":
                    entity_results = await self._sync_companies(job)
                elif entity_type == "deals":
                    entity_results = await self._sync_deals(job)
                else:
                    logger.warning(f"Unknown entity type: {entity_type}")
                    continue
                
                results["entity_results"][entity_type] = entity_results
                results["total_processed"] += entity_results["processed"]
                results["created"] += entity_results["created"]
                results["updated"] += entity_results["updated"]
                results["errors"] += entity_results["errors"]
                
            except Exception as e:
                logger.error(f"Error syncing {entity_type}: {e}")
                results["errors"] += 1
                await self.log_sync_operation(
                    job.id,
                    "ERROR",
                    f"sync_{entity_type}",
                    entity_type,
                    f"Failed to sync {entity_type}: {str(e)}",
                    error={"type": type(e).__name__, "message": str(e)}
                )
        
        return results
    
    async def _sync_contacts(self, job: SyncJob) -> Dict[str, Any]:
        """Sync contacts with HubSpot."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        # Get contacts from HubSpot
        url = f"{self.api_base_url}/crm/v3/objects/contacts"
        params = {
            "limit": 100,
            "properties": "email,firstname,lastname,phone,company,jobtitle"
        }
        
        async for contact in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process contact (implementation would depend on your data model)
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_contact",
                    "contact",
                    f"Processed contact: {contact.get('properties', {}).get('email', 'No email')}",
                    entity_id=contact.get("id"),
                    details={"hubspot_id": contact.get("id")}
                )
                
                # Here you would:
                # 1. Transform HubSpot contact to your internal format
                # 2. Check if contact exists in your system
                # 3. Create or update as needed
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing contact: {e}")
                await self.log_sync_operation(
                    job.id,
                    "ERROR",
                    "process_contact",
                    "contact",
                    f"Failed to process contact: {str(e)}",
                    entity_id=contact.get("id"),
                    error={"type": type(e).__name__, "message": str(e)}
                )
        
        return results
    
    async def _sync_companies(self, job: SyncJob) -> Dict[str, Any]:
        """Sync companies with HubSpot."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        # Get companies from HubSpot
        url = f"{self.api_base_url}/crm/v3/objects/companies"
        params = {
            "limit": 100,
            "properties": "name,domain,industry,phone,city,state,country"
        }
        
        async for company in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process company
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_company",
                    "company",
                    f"Processed company: {company.get('properties', {}).get('name', 'No name')}",
                    entity_id=company.get("id"),
                    details={"hubspot_id": company.get("id")}
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing company: {e}")
        
        return results
    
    async def _sync_deals(self, job: SyncJob) -> Dict[str, Any]:
        """Sync deals with HubSpot."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        # Get deals from HubSpot
        url = f"{self.api_base_url}/crm/v3/objects/deals"
        params = {
            "limit": 100,
            "properties": "dealname,amount,dealstage,closedate,pipeline"
        }
        
        async for deal in self.paginate_api_results("GET", url, params):
            try:
                results["processed"] += 1
                
                # Process deal
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    "process_deal",
                    "deal",
                    f"Processed deal: {deal.get('properties', {}).get('dealname', 'No name')}",
                    entity_id=deal.get("id"),
                    details={"hubspot_id": deal.get("id")}
                )
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing deal: {e}")
        
        return results
    
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle HubSpot webhook."""
        logger.info(f"Handling HubSpot webhook: {event_type}")
        
        # Process webhook based on event type
        if event_type == "contact.creation":
            await self._handle_contact_created(payload)
        elif event_type == "contact.deletion":
            await self._handle_contact_deleted(payload)
        elif event_type == "contact.propertyChange":
            await self._handle_contact_updated(payload)
        elif event_type == "company.creation":
            await self._handle_company_created(payload)
        elif event_type == "deal.creation":
            await self._handle_deal_created(payload)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
    
    async def _handle_contact_created(self, payload: Dict[str, Any]) -> None:
        """Handle contact creation webhook."""
        contact_id = payload.get("objectId")
        logger.info(f"Contact created: {contact_id}")
        # Implement contact creation logic
    
    async def _handle_contact_deleted(self, payload: Dict[str, Any]) -> None:
        """Handle contact deletion webhook."""
        contact_id = payload.get("objectId")
        logger.info(f"Contact deleted: {contact_id}")
        # Implement contact deletion logic
    
    async def _handle_contact_updated(self, payload: Dict[str, Any]) -> None:
        """Handle contact update webhook."""
        contact_id = payload.get("objectId")
        logger.info(f"Contact updated: {contact_id}")
        # Implement contact update logic
    
    async def _handle_company_created(self, payload: Dict[str, Any]) -> None:
        """Handle company creation webhook."""
        company_id = payload.get("objectId")
        logger.info(f"Company created: {company_id}")
        # Implement company creation logic
    
    async def _handle_deal_created(self, payload: Dict[str, Any]) -> None:
        """Handle deal creation webhook."""
        deal_id = payload.get("objectId")
        logger.info(f"Deal created: {deal_id}")
        # Implement deal creation logic
    
    def verify_webhook_signature(self, signature: str, payload: bytes) -> bool:
        """Verify HubSpot webhook signature."""
        if not settings.webhook_secret:
            logger.warning("No webhook secret configured")
            return False
        
        expected_signature = hmac.new(
            settings.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, f"sha256={expected_signature}")
    
    def extract_results_from_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract results from HubSpot API response."""
        return data.get("results", [])
    
    def has_more_pages(self, data: Dict[str, Any], current_page: int) -> bool:
        """Check if there are more pages in HubSpot response."""
        paging = data.get("paging", {})
        return "next" in paging and paging["next"] is not None