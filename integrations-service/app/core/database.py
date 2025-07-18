"""Database connections and utilities."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Database:
    """Database connection manager."""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            self.db = self.client[settings.mongodb_db_name]
            
            # Test connection
            await self.client.admin.command("ping")
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_collection(self, name: str):
        """Get a collection."""
        if not self.db:
            raise RuntimeError("Database not connected")
        return self.db[name]


# Global database instance
database = Database()


# Collection names
COLLECTIONS = {
    "integrations": "integrations",
    "sync_jobs": "sync_jobs",
    "sync_logs": "sync_logs",
    "webhook_events": "webhook_events",
}