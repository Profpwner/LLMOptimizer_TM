"""Salesforce integration implementation."""

import json
import hmac
import hashlib
import jwt
import time
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime, timedelta
import urllib.parse
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from app.integrations.base import BaseIntegration, IntegrationError, AuthenticationError
from app.integrations.registry import IntegrationRegistry
from app.models import IntegrationType, OAuthToken, SyncJob
from app.core.config import get_settings, INTEGRATION_CONFIGS
from app.utils.crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()


@IntegrationRegistry.register(IntegrationType.SALESFORCE)
class SalesforceIntegration(BaseIntegration):
    """Salesforce CRM integration supporting OAuth 2.0 and JWT Bearer flow."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = INTEGRATION_CONFIGS["salesforce"]
        self.api_version = self.config["api_version"]
        self._instance_url = None
        self._composite_batch_size = 25  # Salesforce composite API limit
        
    @property
    async def instance_url(self) -> str:
        """Get Salesforce instance URL."""
        if not self._instance_url:
            await self.ensure_authenticated()
            if self.integration.config.api_endpoint:
                self._instance_url = self.integration.config.api_endpoint
            else:
                # Get instance URL from token response
                token_info = await self._get_token_info()
                self._instance_url = token_info.get("instance_url")
        return self._instance_url
    
    async def get_authorization_url(self, state: str) -> str:
        """Generate Salesforce OAuth authorization URL."""
        params = {
            "response_type": "code",
            "client_id": settings.salesforce_client_id,
            "redirect_uri": settings.salesforce_redirect_uri,
            "scope": " ".join(self.config["scopes"]),
            "state": state,
        }
        return f"{self.config['auth_url']}?{urllib.parse.urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.salesforce_client_id,
            "client_secret": settings.salesforce_client_secret,
            "redirect_uri": settings.salesforce_redirect_uri,
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
        
        # Store instance URL in integration config
        if "instance_url" in token_data:
            self.integration.config.api_endpoint = token_data["instance_url"]
            self._instance_url = token_data["instance_url"]
        
        # Calculate expiration (Salesforce tokens don't expire but we'll set a long expiry)
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        return OAuthToken(
            access_token=encrypt_token(token_data["access_token"], settings.encryption_key),
            refresh_token=encrypt_token(token_data["refresh_token"], settings.encryption_key) if "refresh_token" in token_data else None,
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
            encrypted=True,
        )
    
    async def refresh_access_token(self) -> OAuthToken:
        """Refresh Salesforce access token."""
        if not self.integration.oauth_token or not self.integration.oauth_token.refresh_token:
            raise AuthenticationError("No refresh token available")
        
        refresh_token = decrypt_token(
            self.integration.oauth_token.refresh_token,
            settings.encryption_key
        ) if self.integration.oauth_token.encrypted else self.integration.oauth_token.refresh_token
        
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.salesforce_client_id,
            "client_secret": settings.salesforce_client_secret,
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
        
        # Update instance URL if provided
        if "instance_url" in token_data:
            self.integration.config.api_endpoint = token_data["instance_url"]
            self._instance_url = token_data["instance_url"]
        
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        return OAuthToken(
            access_token=encrypt_token(token_data["access_token"], settings.encryption_key),
            refresh_token=self.integration.oauth_token.refresh_token,  # Salesforce doesn't rotate refresh tokens
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
            encrypted=True,
        )
    
    async def _get_jwt_bearer_token(self, username: str, private_key: str) -> OAuthToken:
        """Get access token using JWT Bearer flow."""
        # Create JWT
        claim = {
            "iss": settings.salesforce_client_id,
            "sub": username,
            "aud": "https://login.salesforce.com",
            "exp": int(time.time()) + 300  # 5 minutes
        }
        
        # Load private key
        private_key_obj = serialization.load_pem_private_key(
            private_key.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Sign JWT
        assertion = jwt.encode(
            claim,
            private_key_obj,
            algorithm="RS256"
        )
        
        # Exchange for access token
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion
        }
        
        response = await self.http_client.post(
            self.config["token_url"],
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        if response.status_code != 200:
            raise AuthenticationError(f"JWT Bearer token exchange failed: {response.text}")
        
        token_data = response.json()
        
        # Store instance URL
        if "instance_url" in token_data:
            self.integration.config.api_endpoint = token_data["instance_url"]
            self._instance_url = token_data["instance_url"]
        
        expires_at = datetime.utcnow() + timedelta(hours=2)
        
        return OAuthToken(
            access_token=encrypt_token(token_data["access_token"], settings.encryption_key),
            refresh_token=None,  # JWT Bearer flow doesn't provide refresh tokens
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope", ""),
            encrypted=True,
        )
    
    async def _get_token_info(self) -> Dict[str, Any]:
        """Get token info including instance URL."""
        token = decrypt_token(
            self.integration.oauth_token.access_token,
            settings.encryption_key
        ) if self.integration.oauth_token.encrypted else self.integration.oauth_token.access_token
        
        response = await self.http_client.get(
            f"{self.config['token_url']}/introspect",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        if response.status_code == 200:
            return response.json()
        return {}
    
    async def test_connection(self) -> bool:
        """Test Salesforce connection."""
        try:
            instance_url = await self.instance_url
            response = await self.make_api_request(
                "GET",
                f"{instance_url}/services/data/{self.api_version}/"
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def sync_data(self, job: SyncJob) -> Dict[str, Any]:
        """Sync data with Salesforce."""
        results = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "entity_results": {}
        }
        
        for entity_type in job.entity_types:
            try:
                if entity_type == "leads":
                    entity_results = await self._sync_leads(job)
                elif entity_type == "accounts":
                    entity_results = await self._sync_accounts(job)
                elif entity_type == "opportunities":
                    entity_results = await self._sync_opportunities(job)
                elif entity_type == "contacts":
                    entity_results = await self._sync_contacts(job)
                elif entity_type.startswith("custom:"):
                    # Handle custom objects
                    custom_object = entity_type.split(":", 1)[1]
                    entity_results = await self._sync_custom_object(job, custom_object)
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
    
    async def _sync_leads(self, job: SyncJob) -> Dict[str, Any]:
        """Sync leads with Salesforce."""
        return await self._sync_sobject(job, "Lead", [
            "Id", "FirstName", "LastName", "Email", "Phone", "Company",
            "Title", "Status", "Rating", "Website", "Industry"
        ])
    
    async def _sync_accounts(self, job: SyncJob) -> Dict[str, Any]:
        """Sync accounts with Salesforce."""
        return await self._sync_sobject(job, "Account", [
            "Id", "Name", "Type", "Industry", "Website", "Phone",
            "BillingCity", "BillingState", "BillingCountry", "AnnualRevenue"
        ])
    
    async def _sync_opportunities(self, job: SyncJob) -> Dict[str, Any]:
        """Sync opportunities with Salesforce."""
        return await self._sync_sobject(job, "Opportunity", [
            "Id", "Name", "AccountId", "Amount", "StageName", "CloseDate",
            "Probability", "Type", "LeadSource", "NextStep"
        ])
    
    async def _sync_contacts(self, job: SyncJob) -> Dict[str, Any]:
        """Sync contacts with Salesforce."""
        return await self._sync_sobject(job, "Contact", [
            "Id", "FirstName", "LastName", "Email", "Phone", "AccountId",
            "Title", "Department", "MailingCity", "MailingState"
        ])
    
    async def _sync_custom_object(self, job: SyncJob, object_name: str) -> Dict[str, Any]:
        """Sync custom object with Salesforce."""
        # First, describe the object to get fields
        instance_url = await self.instance_url
        describe_response = await self.make_api_request(
            "GET",
            f"{instance_url}/services/data/{self.api_version}/sobjects/{object_name}/describe"
        )
        
        if describe_response.status_code != 200:
            raise IntegrationError(f"Failed to describe object {object_name}")
        
        describe_data = describe_response.json()
        
        # Get queryable fields
        fields = [
            field["name"] for field in describe_data["fields"]
            if field["type"] not in ["address", "location"] and not field["calculated"]
        ][:50]  # Limit to 50 fields to avoid query length issues
        
        return await self._sync_sobject(job, object_name, fields)
    
    async def _sync_sobject(self, job: SyncJob, object_type: str, fields: List[str]) -> Dict[str, Any]:
        """Generic sync for Salesforce objects."""
        results = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        
        instance_url = await self.instance_url
        
        # Build SOQL query
        query = f"SELECT {', '.join(fields)} FROM {object_type}"
        
        # Add filters if provided
        if job.filters:
            where_clauses = []
            for field, value in job.filters.items():
                if isinstance(value, str):
                    where_clauses.append(f"{field} = '{value}'")
                elif isinstance(value, (int, float)):
                    where_clauses.append(f"{field} = {value}")
                elif isinstance(value, bool):
                    where_clauses.append(f"{field} = {str(value).lower()}")
            
            if where_clauses:
                query += f" WHERE {' AND '.join(where_clauses)}"
        
        # Add ordering and limit
        query += " ORDER BY Id"
        
        # Execute query with pagination
        async for record in self._query_salesforce(query):
            try:
                results["processed"] += 1
                
                # Process record
                await self.log_sync_operation(
                    job.id,
                    "INFO",
                    f"process_{object_type.lower()}",
                    object_type,
                    f"Processed {object_type}: {record.get('Id')}",
                    entity_id=record.get("Id"),
                    details={"salesforce_id": record.get("Id")}
                )
                
                # Here you would:
                # 1. Transform Salesforce record to your internal format
                # 2. Check if record exists in your system
                # 3. Create or update as needed
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error processing {object_type}: {e}")
                await self.log_sync_operation(
                    job.id,
                    "ERROR",
                    f"process_{object_type.lower()}",
                    object_type,
                    f"Failed to process {object_type}: {str(e)}",
                    entity_id=record.get("Id"),
                    error={"type": type(e).__name__, "message": str(e)}
                )
        
        return results
    
    async def _query_salesforce(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        """Execute SOQL query with pagination."""
        instance_url = await self.instance_url
        
        # URL encode the query
        encoded_query = urllib.parse.quote(query)
        next_url = f"{instance_url}/services/data/{self.api_version}/query?q={encoded_query}"
        
        while next_url:
            response = await self.make_api_request("GET", next_url)
            
            if response.status_code != 200:
                raise IntegrationError(f"Query failed: {response.text}")
            
            data = response.json()
            
            # Yield records
            for record in data.get("records", []):
                yield record
            
            # Check for more records
            if data.get("done", True):
                break
            
            # Get next batch URL
            next_url = f"{instance_url}{data.get('nextRecordsUrl', '')}" if data.get("nextRecordsUrl") else None
    
    async def bulk_create_records(self, object_type: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple records using Composite API."""
        instance_url = await self.instance_url
        results = {"success": 0, "errors": 0, "results": []}
        
        # Process in batches
        for i in range(0, len(records), self._composite_batch_size):
            batch = records[i:i + self._composite_batch_size]
            
            # Build composite request
            composite_request = {
                "allOrNone": False,
                "records": [
                    {
                        "attributes": {"type": object_type},
                        **record
                    }
                    for record in batch
                ]
            }
            
            response = await self.make_api_request(
                "POST",
                f"{instance_url}/services/data/{self.api_version}/composite/sobjects",
                json=composite_request
            )
            
            if response.status_code == 200:
                batch_results = response.json()
                for result in batch_results:
                    if result.get("success"):
                        results["success"] += 1
                    else:
                        results["errors"] += 1
                    results["results"].append(result)
            else:
                results["errors"] += len(batch)
                logger.error(f"Bulk create failed: {response.text}")
        
        return results
    
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle Salesforce webhook (Change Data Capture events)."""
        logger.info(f"Handling Salesforce webhook: {event_type}")
        
        # Salesforce CDC events come through Platform Events
        if "data" in payload and "event" in payload["data"]:
            event = payload["data"]["event"]
            event_type = event.get("type", "")
            
            if event_type == "created":
                await self._handle_record_created(event)
            elif event_type == "updated":
                await self._handle_record_updated(event)
            elif event_type == "deleted":
                await self._handle_record_deleted(event)
            elif event_type == "undeleted":
                await self._handle_record_undeleted(event)
            else:
                logger.warning(f"Unknown CDC event type: {event_type}")
    
    async def _handle_record_created(self, event: Dict[str, Any]) -> None:
        """Handle record creation event."""
        object_type = event.get("objectType")
        record_id = event.get("recordId")
        logger.info(f"{object_type} created: {record_id}")
        # Implement record creation logic
    
    async def _handle_record_updated(self, event: Dict[str, Any]) -> None:
        """Handle record update event."""
        object_type = event.get("objectType")
        record_id = event.get("recordId")
        changed_fields = event.get("changedFields", [])
        logger.info(f"{object_type} updated: {record_id}, fields: {changed_fields}")
        # Implement record update logic
    
    async def _handle_record_deleted(self, event: Dict[str, Any]) -> None:
        """Handle record deletion event."""
        object_type = event.get("objectType")
        record_id = event.get("recordId")
        logger.info(f"{object_type} deleted: {record_id}")
        # Implement record deletion logic
    
    async def _handle_record_undeleted(self, event: Dict[str, Any]) -> None:
        """Handle record undeletion event."""
        object_type = event.get("objectType")
        record_id = event.get("recordId")
        logger.info(f"{object_type} undeleted: {record_id}")
        # Implement record undeletion logic
    
    def verify_webhook_signature(self, signature: str, payload: bytes) -> bool:
        """Verify Salesforce webhook signature."""
        if not settings.webhook_secret:
            logger.warning("No webhook secret configured")
            return False
        
        # Salesforce uses HMAC-SHA256
        expected_signature = hmac.new(
            settings.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def extract_results_from_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract results from Salesforce API response."""
        if "records" in data:
            return data["records"]
        elif "results" in data:
            return data["results"]
        elif isinstance(data, list):
            return data
        return []
    
    def has_more_pages(self, data: Dict[str, Any], current_page: int) -> bool:
        """Check if there are more pages in Salesforce response."""
        # Salesforce uses 'done' field and 'nextRecordsUrl'
        if isinstance(data, dict):
            return not data.get("done", True) and "nextRecordsUrl" in data
        return False
    
    async def setup_change_data_capture(self, objects: List[str]) -> bool:
        """Setup Change Data Capture for specified objects."""
        instance_url = await self.instance_url
        
        # Enable CDC for objects
        cdc_config = {
            "FullName": "ChangeDataCapture",
            "entities": {
                "entity": [{"name": obj} for obj in objects]
            }
        }
        
        response = await self.make_api_request(
            "POST",
            f"{instance_url}/services/data/{self.api_version}/tooling/sobjects/PlatformEventChannelMember",
            json=cdc_config
        )
        
        return response.status_code in [200, 201]
    
    async def get_field_metadata(self, object_type: str) -> List[Dict[str, Any]]:
        """Get field metadata for an object."""
        instance_url = await self.instance_url
        
        response = await self.make_api_request(
            "GET",
            f"{instance_url}/services/data/{self.api_version}/sobjects/{object_type}/describe"
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("fields", [])
        return []
    
    async def execute_apex(self, apex_code: str) -> Dict[str, Any]:
        """Execute anonymous Apex code."""
        instance_url = await self.instance_url
        
        response = await self.make_api_request(
            "GET",
            f"{instance_url}/services/data/{self.api_version}/tooling/executeAnonymous",
            params={"anonymousBody": apex_code}
        )
        
        if response.status_code == 200:
            return response.json()
        raise IntegrationError(f"Apex execution failed: {response.text}")