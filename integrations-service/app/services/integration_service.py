"""Integration service for managing integrations."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from bson import ObjectId
import logging
import redis.asyncio as redis

from app.core.database import Database, COLLECTIONS
from app.core.config import get_settings
from app.models import Integration, IntegrationStatus, OAuthToken
from app.integrations.registry import IntegrationRegistry
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)
settings = get_settings()


class IntegrationService:
    """Service for managing integrations."""
    
    def __init__(self, db: Database):
        self.db = db
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    
    async def create_integration(self, integration: Integration) -> Integration:
        """Create a new integration."""
        collection = self.db.get_collection(COLLECTIONS["integrations"])
        
        # Convert to dict and insert
        integration_dict = integration.dict(by_alias=True, exclude={"id"})
        result = await collection.insert_one(integration_dict)
        
        # Set the ID and return
        integration.id = str(result.inserted_id)
        logger.info(f"Created integration {integration.id} of type {integration.integration_type}")
        
        return integration
    
    async def get_integration(self, integration_id: str) -> Optional[Integration]:
        """Get integration by ID."""
        collection = self.db.get_collection(COLLECTIONS["integrations"])
        
        try:
            doc = await collection.find_one({"_id": ObjectId(integration_id)})
            if doc:
                return Integration(**doc)
        except Exception as e:
            logger.error(f"Error getting integration {integration_id}: {e}")
        
        return None
    
    async def list_integrations(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 10
    ) -> List[Integration]:
        """List integrations with filters."""
        collection = self.db.get_collection(COLLECTIONS["integrations"])
        
        cursor = collection.find(filters).skip(skip).limit(limit)
        integrations = []
        
        async for doc in cursor:
            integrations.append(Integration(**doc))
        
        return integrations
    
    async def count_integrations(self, filters: Dict[str, Any]) -> int:
        """Count integrations with filters."""
        collection = self.db.get_collection(COLLECTIONS["integrations"])
        return await collection.count_documents(filters)
    
    async def update_integration(
        self,
        integration_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Integration]:
        """Update an integration."""
        collection = self.db.get_collection(COLLECTIONS["integrations"])
        
        # Add updated_at timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update document
        result = await collection.update_one(
            {"_id": ObjectId(integration_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return await self.get_integration(integration_id)
        
        return None
    
    async def delete_integration(self, integration_id: str) -> bool:
        """Delete an integration."""
        collection = self.db.get_collection(COLLECTIONS["integrations"])
        
        result = await collection.delete_one({"_id": ObjectId(integration_id)})
        
        if result.deleted_count > 0:
            logger.info(f"Deleted integration {integration_id}")
            return True
        
        return False
    
    async def get_oauth_authorization_url(
        self,
        integration: Integration,
        state: str
    ) -> str:
        """Get OAuth authorization URL for an integration."""
        # Get integration class
        integration_class = IntegrationRegistry.get(integration.integration_type)
        if not integration_class:
            raise ValueError(f"Unknown integration type: {integration.integration_type}")
        
        # Create integration instance
        async with integration_class(integration) as impl:
            return await impl.get_authorization_url(state)
    
    async def complete_oauth_flow(
        self,
        integration: Integration,
        code: str
    ) -> Integration:
        """Complete OAuth flow by exchanging code for token."""
        # Get integration class
        integration_class = IntegrationRegistry.get(integration.integration_type)
        if not integration_class:
            raise ValueError(f"Unknown integration type: {integration.integration_type}")
        
        # Create integration instance
        async with integration_class(integration) as impl:
            # Exchange code for token
            token = await impl.exchange_code_for_token(code)
            
            # Update integration with token
            integration.oauth_token = token
            integration.status = IntegrationStatus.CONNECTED
            integration.updated_at = datetime.utcnow()
            
            # Save to database
            await self.update_integration(
                integration.id,
                {
                    "oauth_token": token.dict(),
                    "status": integration.status,
                    "updated_at": integration.updated_at,
                }
            )
            
            logger.info(f"OAuth flow completed for integration {integration.id}")
            
        return integration
    
    async def test_integration_connection(
        self,
        integration: Integration
    ) -> Tuple[bool, str]:
        """Test if integration connection is valid."""
        # Get integration class
        integration_class = IntegrationRegistry.get(integration.integration_type)
        if not integration_class:
            return False, f"Unknown integration type: {integration.integration_type}"
        
        try:
            # Create integration instance and test
            async with integration_class(integration) as impl:
                is_connected = await impl.test_connection()
                
                if is_connected:
                    # Update status if needed
                    if integration.status != IntegrationStatus.CONNECTED:
                        await self.update_integration(
                            integration.id,
                            {"status": IntegrationStatus.CONNECTED}
                        )
                    return True, "Connection successful"
                else:
                    # Update status if needed
                    if integration.status == IntegrationStatus.CONNECTED:
                        await self.update_integration(
                            integration.id,
                            {"status": IntegrationStatus.DISCONNECTED}
                        )
                    return False, "Connection failed"
                    
        except Exception as e:
            logger.error(f"Connection test failed for integration {integration.id}: {e}")
            # Update status and error message
            await self.update_integration(
                integration.id,
                {
                    "status": IntegrationStatus.ERROR,
                    "error_message": str(e),
                }
            )
            return False, f"Connection test failed: {str(e)}"
    
    async def disconnect_integration(self, integration_id: str) -> None:
        """Disconnect an integration by removing auth tokens."""
        await self.update_integration(
            integration_id,
            {
                "oauth_token": None,
                "api_key": None,
                "status": IntegrationStatus.DISCONNECTED,
                "error_message": None,
            }
        )
        logger.info(f"Disconnected integration {integration_id}")
    
    async def store_oauth_state(
        self,
        state: str,
        integration_id: str,
        user_id: str,
        ttl: int = 600  # 10 minutes
    ) -> None:
        """Store OAuth state in Redis for verification."""
        key = f"oauth_state:{state}"
        value = {
            "integration_id": integration_id,
            "user_id": user_id,
        }
        
        await self.redis_client.setex(
            key,
            ttl,
            json.dumps(value)
        )
    
    async def verify_oauth_state(self, state: str) -> Optional[Dict[str, str]]:
        """Verify OAuth state and return associated data."""
        import json
        
        key = f"oauth_state:{state}"
        value = await self.redis_client.get(key)
        
        if value:
            # Delete the state after verification
            await self.redis_client.delete(key)
            return json.loads(value)
        
        return None