"""MongoDB client with async support and multi-tenancy."""

import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Type, TypeVar, Union
from datetime import datetime

import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
from pymongo.errors import DuplicateKeyError, OperationFailure
from beanie import init_beanie, Document
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import MongoDBConfig, db_config
from database.schemas.mongodb.models import (
    ContentDocument, OptimizationResult, AnalyticsEvent,
    ContentPerformance, AIModelUsage
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Document)


class MongoDBClient:
    """Async MongoDB client with multi-tenancy support."""
    
    def __init__(self, config: Optional[MongoDBConfig] = None):
        """Initialize MongoDB client."""
        self.config = config or db_config.mongodb
        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize MongoDB connection and Beanie ODM."""
        # Create motor client with connection pooling
        self._client = AsyncIOMotorClient(
            self.config.url,
            maxPoolSize=self.config.max_pool_size,
            minPoolSize=self.config.min_pool_size,
            serverSelectionTimeoutMS=5000,
        )
        
        # Get database
        self._database = self._client[self.config.database]
        
        # Initialize Beanie with document models
        await init_beanie(
            database=self._database,
            document_models=[
                ContentDocument,
                OptimizationResult,
                AnalyticsEvent,
                ContentPerformance,
                AIModelUsage,
            ]
        )
        
        # Create indexes
        await self._create_indexes()
        
        self._initialized = True
        logger.info("MongoDB client initialized successfully")
    
    async def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
        logger.info("MongoDB client closed")
    
    async def _create_indexes(self):
        """Create necessary indexes for all collections."""
        # Indexes are already defined in the Document models
        # This method can be used for additional custom indexes
        
        # Create TTL indexes for time-series data
        analytics_collection = self._database.analytics_events
        await analytics_collection.create_index(
            [("timestamp", DESCENDING)],
            expireAfterSeconds=30 * 24 * 60 * 60  # 30 days
        )
        
        performance_collection = self._database.content_performance
        await performance_collection.create_index(
            [("period_start", DESCENDING)],
            expireAfterSeconds=90 * 24 * 60 * 60  # 90 days
        )
        
        logger.info("MongoDB indexes created")
    
    def get_collection(self, name: str, tenant_id: Optional[str] = None) -> AsyncIOMotorCollection:
        """Get a collection with optional tenant prefix."""
        if tenant_id and self.config.tenant_collection_prefix:
            name = f"tenant_{tenant_id}_{name}"
        return self._database[name]
    
    # Document Operations
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create(self, document: T, tenant_id: Optional[str] = None) -> T:
        """Create a new document."""
        if tenant_id and hasattr(document, 'org_id'):
            document.org_id = tenant_id
        
        try:
            await document.insert()
            return document
        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error: {e}")
            raise
    
    async def create_many(self, documents: List[T], tenant_id: Optional[str] = None) -> List[T]:
        """Create multiple documents in a single operation."""
        if tenant_id:
            for doc in documents:
                if hasattr(doc, 'org_id'):
                    doc.org_id = tenant_id
        
        # Beanie doesn't have bulk insert, so we use motor directly
        collection = self.get_collection(documents[0].Settings.name, tenant_id)
        docs_dict = [doc.dict() for doc in documents]
        
        result = await collection.insert_many(docs_dict)
        
        # Update documents with inserted IDs
        for doc, inserted_id in zip(documents, result.inserted_ids):
            doc.id = inserted_id
        
        return documents
    
    async def get(self, model_class: Type[T], id: str, tenant_id: Optional[str] = None) -> Optional[T]:
        """Get a document by ID."""
        filters = {"_id": id}
        if tenant_id and hasattr(model_class, 'org_id'):
            filters["org_id"] = tenant_id
        
        return await model_class.find_one(filters)
    
    async def get_many(self, model_class: Type[T], filters: Dict[str, Any],
                      tenant_id: Optional[str] = None, limit: int = 100,
                      skip: int = 0, sort: Optional[List[tuple]] = None) -> List[T]:
        """Get multiple documents with filters."""
        if tenant_id:
            filters["org_id"] = tenant_id
        
        query = model_class.find(filters)
        
        if sort:
            query = query.sort(sort)
        
        query = query.skip(skip).limit(limit)
        
        return await query.to_list()
    
    async def update(self, document: T, updates: Dict[str, Any], tenant_id: Optional[str] = None) -> T:
        """Update a document."""
        # Verify tenant access
        if tenant_id and hasattr(document, 'org_id') and document.org_id != tenant_id:
            raise PermissionError("Access denied to this resource")
        
        # Apply updates to document
        for key, value in updates.items():
            if hasattr(document, key) and key not in ['id', '_id', 'org_id']:
                setattr(document, key, value)
        
        # Update timestamp
        if hasattr(document, 'updated_at'):
            document.updated_at = datetime.utcnow()
        
        await document.save()
        return document
    
    async def update_many(self, model_class: Type[T], filters: Dict[str, Any],
                         updates: Dict[str, Any], tenant_id: Optional[str] = None) -> int:
        """Update multiple documents."""
        if tenant_id:
            filters["org_id"] = tenant_id
        
        # Add updated_at timestamp
        updates["$set"] = updates.get("$set", {})
        updates["$set"]["updated_at"] = datetime.utcnow()
        
        result = await model_class.update_many(filters, updates)
        return result.modified_count
    
    async def delete(self, document: T, tenant_id: Optional[str] = None) -> bool:
        """Delete a document."""
        # Verify tenant access
        if tenant_id and hasattr(document, 'org_id') and document.org_id != tenant_id:
            raise PermissionError("Access denied to this resource")
        
        await document.delete()
        return True
    
    async def delete_many(self, model_class: Type[T], filters: Dict[str, Any],
                         tenant_id: Optional[str] = None) -> int:
        """Delete multiple documents."""
        if tenant_id:
            filters["org_id"] = tenant_id
        
        result = await model_class.delete_many(filters)
        return result.deleted_count
    
    # Aggregation Operations
    async def aggregate(self, model_class: Type[T], pipeline: List[Dict[str, Any]],
                       tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute an aggregation pipeline."""
        # Add tenant filter to pipeline if needed
        if tenant_id:
            pipeline.insert(0, {"$match": {"org_id": tenant_id}})
        
        collection = self.get_collection(model_class.Settings.name, tenant_id)
        cursor = collection.aggregate(pipeline)
        return await cursor.to_list(length=None)
    
    # Text Search
    async def text_search(self, model_class: Type[T], search_text: str,
                         tenant_id: Optional[str] = None, limit: int = 50) -> List[T]:
        """Perform text search on a collection."""
        filters = {"$text": {"$search": search_text}}
        if tenant_id:
            filters["org_id"] = tenant_id
        
        # Add text score for sorting
        query = model_class.find(filters, {"score": {"$meta": "textScore"}})
        query = query.sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        return await query.to_list()
    
    # Specialized Content Operations
    async def get_content_by_slug(self, org_id: str, slug: str) -> Optional[ContentDocument]:
        """Get content by organization and slug."""
        return await ContentDocument.find_one({
            "org_id": org_id,
            "slug": slug
        })
    
    async def get_latest_content_version(self, content_id: str, org_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest version of a content item."""
        content = await ContentDocument.find_one({
            "_id": content_id,
            "org_id": org_id
        })
        
        if content and content.versions:
            return content.versions[-1].dict()
        return None
    
    async def add_content_version(self, content_id: str, version_data: Dict[str, Any],
                                 org_id: str) -> bool:
        """Add a new version to a content document."""
        content = await ContentDocument.find_one({
            "_id": content_id,
            "org_id": org_id
        })
        
        if not content:
            return False
        
        # Create new version
        from database.schemas.mongodb.models import ContentVersion
        new_version = ContentVersion(**version_data)
        new_version.version_number = len(content.versions) + 1
        
        # Update content
        content.versions.append(new_version)
        content.current_version = new_version.version_number
        content.updated_at = datetime.utcnow()
        
        await content.save()
        return True
    
    # Analytics Operations
    async def track_event(self, event_data: Dict[str, Any], org_id: str) -> AnalyticsEvent:
        """Track an analytics event."""
        event = AnalyticsEvent(org_id=org_id, **event_data)
        await event.insert()
        return event
    
    async def get_content_analytics(self, content_id: str, org_id: str,
                                   start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get analytics for a content item."""
        pipeline = [
            {
                "$match": {
                    "org_id": org_id,
                    "content_id": content_id,
                    "timestamp": {
                        "$gte": start_date,
                        "$lte": end_date
                    }
                }
            },
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1},
                    "unique_users": {"$addToSet": "$user_id"}
                }
            },
            {
                "$project": {
                    "event_type": "$_id",
                    "count": 1,
                    "unique_users": {"$size": "$unique_users"}
                }
            }
        ]
        
        return await self.aggregate(AnalyticsEvent, pipeline, org_id)
    
    # Performance Monitoring
    async def get_collection_stats(self, collection_name: str,
                                  tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a collection."""
        collection = self.get_collection(collection_name, tenant_id)
        
        # Get collection stats
        stats = await self._database.command("collStats", collection.name)
        
        # Get index stats
        index_stats = []
        async for index in collection.list_indexes():
            index_stats.append(index)
        
        return {
            "documents": stats.get("count", 0),
            "size_bytes": stats.get("size", 0),
            "avg_doc_size": stats.get("avgObjSize", 0),
            "indexes": index_stats,
            "index_size_bytes": stats.get("totalIndexSize", 0)
        }
    
    async def get_slow_queries(self, threshold_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get slow queries from MongoDB profiler."""
        threshold = threshold_ms or db_config.postgresql.slow_query_threshold_ms
        
        # Enable profiling if not already enabled
        await self._database.command("profile", 1, slowms=threshold)
        
        # Query system.profile collection
        profile_collection = self._database.system.profile
        cursor = profile_collection.find({
            "millis": {"$gt": threshold}
        }).sort("millis", -1).limit(50)
        
        return await cursor.to_list(length=50)
    
    # Backup and Restore Helpers
    async def export_collection(self, model_class: Type[T], tenant_id: str,
                              filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Export all documents from a collection for a tenant."""
        export_filters = {"org_id": tenant_id}
        if filters:
            export_filters.update(filters)
        
        documents = await model_class.find(export_filters).to_list()
        return [doc.dict() for doc in documents]
    
    async def import_collection(self, model_class: Type[T], documents: List[Dict[str, Any]],
                              tenant_id: str) -> int:
        """Import documents into a collection for a tenant."""
        # Ensure all documents have the correct org_id
        for doc in documents:
            doc["org_id"] = tenant_id
            # Remove _id to allow MongoDB to generate new ones
            doc.pop("_id", None)
        
        # Create document instances
        doc_instances = [model_class(**doc) for doc in documents]
        
        # Insert all documents
        await self.create_many(doc_instances, tenant_id)
        
        return len(doc_instances)


# Global client instance
mongodb_client = MongoDBClient()