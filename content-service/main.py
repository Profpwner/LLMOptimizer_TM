import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List
from enum import Enum

from fastapi import FastAPI, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest
from pythonjsonlogger import jsonlogger
from bson import ObjectId
import uvicorn

# Import routers
from src.api import content_input
from src.services.websocket_manager import manager

# Configure logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Database connections
mongo_client: Optional[AsyncIOMotorClient] = None
redis_client: Optional[redis.Redis] = None

# Metrics
content_created = Counter('content_created_total', 'Total number of content items created')
content_updated = Counter('content_updated_total', 'Total number of content items updated')
content_deleted = Counter('content_deleted_total', 'Total number of content items deleted')
request_duration = Histogram('content_request_duration_seconds', 'Content request duration')

# Enums
class ContentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class ContentType(str, Enum):
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    PRODUCT_DESCRIPTION = "product_description"
    SOCIAL_MEDIA = "social_media"
    EMAIL = "email"
    LANDING_PAGE = "landing_page"

# Models
class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content_type: ContentType
    original_content: str = Field(..., min_length=1)
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = []
    metadata: Optional[dict] = {}

class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    original_content: Optional[str] = Field(None, min_length=1)
    optimized_content: Optional[str] = None
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[dict] = None
    status: Optional[ContentStatus] = None

class Content(BaseModel):
    id: str
    user_id: str
    title: str
    content_type: ContentType
    original_content: str
    optimized_content: Optional[str] = None
    target_audience: Optional[str] = None
    keywords: List[str] = []
    metadata: dict = {}
    status: ContentStatus = ContentStatus.DRAFT
    optimization_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ContentList(BaseModel):
    items: List[Content]
    total: int
    page: int
    page_size: int

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global mongo_client, redis_client
    
    # MongoDB connection
    mongo_url = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
    mongo_client = AsyncIOMotorClient(mongo_url)
    app.state.db = mongo_client.llmoptimizer
    
    # Redis connection
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = await redis.from_url(redis_url)
    app.state.redis = redis_client
    
    # Create indexes
    await app.state.db.content.create_index([("user_id", 1)])
    await app.state.db.content.create_index([("status", 1)])
    await app.state.db.content.create_index([("created_at", -1)])
    
    logger.info("Content service started")
    yield
    
    # Shutdown
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()
    logger.info("Content service stopped")

# Create FastAPI app
app = FastAPI(
    title="Content Service",
    description="Content management service for LLMOptimizer",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(content_input.router)

# Mock authentication dependency (in production, validate with auth service)
async def get_current_user():
    # TODO: Implement proper JWT validation
    return {"id": "user123", "email": "user@example.com"}

# Helper function to serialize MongoDB documents
def serialize_content(content_dict: dict) -> dict:
    content_dict["id"] = str(content_dict.pop("_id"))
    return content_dict

# Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "content-service",
        "version": "1.0.0"
    }

@app.get("/ready")
async def readiness_check():
    try:
        # Check MongoDB
        await app.state.db.command("ping")
        # Check Redis
        await app.state.redis.ping()
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "error": str(e)}
        )

@app.post("/", response_model=Content)
async def create_content(
    content_data: ContentCreate,
    current_user: dict = Depends(get_current_user)
):
    content_created.inc()
    
    content_dict = {
        "user_id": current_user["id"],
        "title": content_data.title,
        "content_type": content_data.content_type,
        "original_content": content_data.original_content,
        "optimized_content": None,
        "target_audience": content_data.target_audience,
        "keywords": content_data.keywords,
        "metadata": content_data.metadata,
        "status": ContentStatus.DRAFT,
        "optimization_score": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await app.state.db.content.insert_one(content_dict)
    content_dict["_id"] = result.inserted_id
    
    # Cache in Redis
    await app.state.redis.setex(
        f"content:{result.inserted_id}",
        3600,  # 1 hour cache
        Content(**serialize_content(content_dict)).model_dump_json()
    )
    
    logger.info(f"Content created: {result.inserted_id}")
    return Content(**serialize_content(content_dict))

@app.get("/", response_model=ContentList)
async def list_content(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[ContentStatus] = None,
    content_type: Optional[ContentType] = None,
    current_user: dict = Depends(get_current_user)
):
    # Build query
    query = {"user_id": current_user["id"]}
    if status:
        query["status"] = status
    if content_type:
        query["content_type"] = content_type
    
    # Get total count
    total = await app.state.db.content.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = app.state.db.content.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    
    items = []
    async for doc in cursor:
        items.append(Content(**serialize_content(doc)))
    
    return ContentList(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )

@app.get("/{content_id}", response_model=Content)
async def get_content(
    content_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Try cache first
    cached = await app.state.redis.get(f"content:{content_id}")
    if cached:
        content_data = Content.model_validate_json(cached)
        if content_data.user_id == current_user["id"]:
            return content_data
    
    # Get from database
    try:
        content = await app.state.db.content.find_one({
            "_id": ObjectId(content_id),
            "user_id": current_user["id"]
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID"
        )
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    content_obj = Content(**serialize_content(content))
    
    # Update cache
    await app.state.redis.setex(
        f"content:{content_id}",
        3600,
        content_obj.model_dump_json()
    )
    
    return content_obj

@app.put("/{content_id}", response_model=Content)
async def update_content(
    content_id: str,
    content_update: ContentUpdate,
    current_user: dict = Depends(get_current_user)
):
    content_updated.inc()
    
    # Build update dict
    update_dict = {
        "updated_at": datetime.utcnow()
    }
    
    if content_update.title is not None:
        update_dict["title"] = content_update.title
    if content_update.original_content is not None:
        update_dict["original_content"] = content_update.original_content
    if content_update.optimized_content is not None:
        update_dict["optimized_content"] = content_update.optimized_content
    if content_update.target_audience is not None:
        update_dict["target_audience"] = content_update.target_audience
    if content_update.keywords is not None:
        update_dict["keywords"] = content_update.keywords
    if content_update.metadata is not None:
        update_dict["metadata"] = content_update.metadata
    if content_update.status is not None:
        update_dict["status"] = content_update.status
    
    # Update in database
    try:
        result = await app.state.db.content.update_one(
            {"_id": ObjectId(content_id), "user_id": current_user["id"]},
            {"$set": update_dict}
        )
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID"
        )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Get updated content
    content = await app.state.db.content.find_one({"_id": ObjectId(content_id)})
    content_obj = Content(**serialize_content(content))
    
    # Update cache
    await app.state.redis.setex(
        f"content:{content_id}",
        3600,
        content_obj.model_dump_json()
    )
    
    logger.info(f"Content updated: {content_id}")
    return content_obj

@app.delete("/{content_id}")
async def delete_content(
    content_id: str,
    current_user: dict = Depends(get_current_user)
):
    content_deleted.inc()
    
    try:
        result = await app.state.db.content.delete_one({
            "_id": ObjectId(content_id),
            "user_id": current_user["id"]
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content ID"
        )
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # Remove from cache
    await app.state.redis.delete(f"content:{content_id}")
    
    logger.info(f"Content deleted: {content_id}")
    return {"message": "Content deleted successfully"}

@app.get("/metrics")
async def metrics():
    return generate_latest()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time content updates"""
    await manager.handle_websocket(websocket, user_id)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development"
    )