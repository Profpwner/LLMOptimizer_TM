import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from enum import Enum

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest
from pythonjsonlogger import jsonlogger
from bson import ObjectId
import pandas as pd
import numpy as np
import uvicorn

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
events_tracked = Counter('analytics_events_tracked_total', 'Total number of events tracked')
reports_generated = Counter('analytics_reports_generated_total', 'Total number of reports generated')
request_duration = Histogram('analytics_request_duration_seconds', 'Analytics request duration')

# Enums
class EventType(str, Enum):
    PAGE_VIEW = "page_view"
    CONTENT_VIEW = "content_view"
    CONTENT_OPTIMIZED = "content_optimized"
    CONVERSION = "conversion"
    ENGAGEMENT = "engagement"
    CLICK = "click"

class MetricType(str, Enum):
    VIEWS = "views"
    CLICKS = "clicks"
    CONVERSIONS = "conversions"
    ENGAGEMENT_RATE = "engagement_rate"
    OPTIMIZATION_SCORE = "optimization_score"
    REVENUE = "revenue"

# Models
class TrackEvent(BaseModel):
    event_type: EventType
    content_id: Optional[str] = None
    user_id: str
    session_id: str
    properties: Dict = Field(default_factory=dict)
    timestamp: Optional[datetime] = None

class AnalyticsEvent(BaseModel):
    id: str
    event_type: EventType
    content_id: Optional[str]
    user_id: str
    session_id: str
    properties: Dict
    timestamp: datetime

class DashboardMetrics(BaseModel):
    total_views: int
    total_clicks: int
    total_conversions: int
    avg_engagement_rate: float
    avg_optimization_score: float
    total_revenue: float
    top_content: List[Dict]
    metrics_by_day: List[Dict]

class AnalyticsReport(BaseModel):
    report_id: str
    user_id: str
    date_range: Dict
    metrics: Dict
    insights: List[str]
    generated_at: datetime

class ReportRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    metrics: List[MetricType]
    group_by: Optional[str] = "day"
    content_ids: Optional[List[str]] = None

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
    await app.state.db.analytics_events.create_index([("user_id", 1)])
    await app.state.db.analytics_events.create_index([("content_id", 1)])
    await app.state.db.analytics_events.create_index([("timestamp", -1)])
    await app.state.db.analytics_events.create_index([("event_type", 1)])
    
    logger.info("Analytics service started")
    yield
    
    # Shutdown
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()
    logger.info("Analytics service stopped")

# Create FastAPI app
app = FastAPI(
    title="Analytics Service",
    description="Analytics and reporting service for LLMOptimizer",
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

# Mock authentication dependency
async def get_current_user():
    # TODO: Implement proper JWT validation
    return {"id": "user123", "email": "user@example.com"}

# Helper functions
def serialize_event(event_dict: dict) -> dict:
    event_dict["id"] = str(event_dict.pop("_id"))
    return event_dict

async def calculate_metrics(user_id: str, start_date: datetime, end_date: datetime, content_ids: Optional[List[str]] = None):
    """Calculate analytics metrics for a given period"""
    query = {
        "user_id": user_id,
        "timestamp": {"$gte": start_date, "$lte": end_date}
    }
    if content_ids:
        query["content_id"] = {"$in": content_ids}
    
    # Get all events
    events = []
    async for event in app.state.db.analytics_events.find(query):
        events.append(event)
    
    if not events:
        return {
            "total_views": 0,
            "total_clicks": 0,
            "total_conversions": 0,
            "avg_engagement_rate": 0.0,
            "avg_optimization_score": 0.0,
            "total_revenue": 0.0
        }
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(events)
    
    metrics = {
        "total_views": len(df[df["event_type"] == EventType.CONTENT_VIEW]),
        "total_clicks": len(df[df["event_type"] == EventType.CLICK]),
        "total_conversions": len(df[df["event_type"] == EventType.CONVERSION]),
        "avg_engagement_rate": 0.0,
        "avg_optimization_score": 0.0,
        "total_revenue": 0.0
    }
    
    # Calculate engagement rate
    if metrics["total_views"] > 0:
        engaged_events = len(df[df["event_type"] == EventType.ENGAGEMENT])
        metrics["avg_engagement_rate"] = (engaged_events / metrics["total_views"]) * 100
    
    # Calculate revenue from conversion events
    conversion_events = df[df["event_type"] == EventType.CONVERSION]
    if not conversion_events.empty:
        metrics["total_revenue"] = conversion_events["properties"].apply(
            lambda x: x.get("revenue", 0) if isinstance(x, dict) else 0
        ).sum()
    
    # Calculate average optimization score
    optimization_events = df[df["event_type"] == EventType.CONTENT_OPTIMIZED]
    if not optimization_events.empty:
        scores = optimization_events["properties"].apply(
            lambda x: x.get("optimization_score", 0) if isinstance(x, dict) else 0
        )
        metrics["avg_optimization_score"] = scores.mean()
    
    return metrics

# Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "analytics-service",
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

@app.post("/track", response_model=AnalyticsEvent)
async def track_event(
    event_data: TrackEvent,
    current_user: dict = Depends(get_current_user)
):
    events_tracked.inc()
    
    # Validate user_id matches current user
    if event_data.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot track events for other users"
        )
    
    event_dict = {
        "event_type": event_data.event_type,
        "content_id": event_data.content_id,
        "user_id": event_data.user_id,
        "session_id": event_data.session_id,
        "properties": event_data.properties,
        "timestamp": event_data.timestamp or datetime.utcnow()
    }
    
    result = await app.state.db.analytics_events.insert_one(event_dict)
    event_dict["_id"] = result.inserted_id
    
    # Update real-time metrics in Redis
    await app.state.redis.hincrby(
        f"metrics:{current_user['id']}:{datetime.utcnow().strftime('%Y-%m-%d')}",
        event_data.event_type,
        1
    )
    
    logger.info(f"Event tracked: {event_data.event_type} for user {event_data.user_id}")
    return AnalyticsEvent(**serialize_event(event_dict))

@app.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(get_current_user)
):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Calculate overall metrics
    metrics = await calculate_metrics(current_user["id"], start_date, end_date)
    
    # Get top performing content
    pipeline = [
        {
            "$match": {
                "user_id": current_user["id"],
                "timestamp": {"$gte": start_date, "$lte": end_date},
                "content_id": {"$ne": None}
            }
        },
        {
            "$group": {
                "_id": "$content_id",
                "views": {
                    "$sum": {
                        "$cond": [{"$eq": ["$event_type", EventType.CONTENT_VIEW]}, 1, 0]
                    }
                },
                "conversions": {
                    "$sum": {
                        "$cond": [{"$eq": ["$event_type", EventType.CONVERSION]}, 1, 0]
                    }
                }
            }
        },
        {"$sort": {"views": -1}},
        {"$limit": 10}
    ]
    
    top_content = []
    async for doc in app.state.db.analytics_events.aggregate(pipeline):
        top_content.append({
            "content_id": doc["_id"],
            "views": doc["views"],
            "conversions": doc["conversions"],
            "conversion_rate": (doc["conversions"] / doc["views"] * 100) if doc["views"] > 0 else 0
        })
    
    # Get metrics by day
    metrics_by_day = []
    for i in range(days):
        day = end_date - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_metrics = await calculate_metrics(current_user["id"], day_start, day_end)
        metrics_by_day.append({
            "date": day_start.isoformat(),
            "metrics": day_metrics
        })
    
    return DashboardMetrics(
        total_views=metrics["total_views"],
        total_clicks=metrics["total_clicks"],
        total_conversions=metrics["total_conversions"],
        avg_engagement_rate=round(metrics["avg_engagement_rate"], 2),
        avg_optimization_score=round(metrics["avg_optimization_score"], 2),
        total_revenue=round(metrics["total_revenue"], 2),
        top_content=top_content,
        metrics_by_day=metrics_by_day
    )

@app.post("/reports", response_model=AnalyticsReport)
async def generate_report(
    report_request: ReportRequest,
    current_user: dict = Depends(get_current_user)
):
    reports_generated.inc()
    
    # Calculate metrics
    metrics = await calculate_metrics(
        current_user["id"],
        report_request.start_date,
        report_request.end_date,
        report_request.content_ids
    )
    
    # Generate insights
    insights = []
    
    if metrics["total_views"] > 0:
        conversion_rate = (metrics["total_conversions"] / metrics["total_views"]) * 100
        insights.append(f"Overall conversion rate: {conversion_rate:.2f}%")
    
    if metrics["avg_optimization_score"] > 0:
        insights.append(f"Average content optimization score: {metrics['avg_optimization_score']:.2f}/100")
    
    if metrics["avg_engagement_rate"] > 50:
        insights.append("High engagement rate indicates strong content performance")
    elif metrics["avg_engagement_rate"] < 20:
        insights.append("Low engagement rate suggests content optimization opportunities")
    
    # Save report
    report_dict = {
        "user_id": current_user["id"],
        "date_range": {
            "start": report_request.start_date.isoformat(),
            "end": report_request.end_date.isoformat()
        },
        "metrics": metrics,
        "insights": insights,
        "generated_at": datetime.utcnow()
    }
    
    result = await app.state.db.analytics_reports.insert_one(report_dict)
    report_dict["report_id"] = str(result.inserted_id)
    
    logger.info(f"Report generated for user {current_user['id']}")
    return AnalyticsReport(**report_dict)

@app.get("/metrics")
async def metrics():
    return generate_latest()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development"
    )