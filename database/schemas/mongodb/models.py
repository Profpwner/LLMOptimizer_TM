"""MongoDB models for content and analytics data."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict
from beanie import Document, Indexed, Link
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT


class ContentType(str, Enum):
    """Content types supported by the platform."""
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    PRODUCT_DESCRIPTION = "product_description"
    LANDING_PAGE = "landing_page"
    EMAIL = "email"
    SOCIAL_MEDIA = "social_media"
    AD_COPY = "ad_copy"
    OTHER = "other"


class OptimizationType(str, Enum):
    """Types of content optimization."""
    SEO = "seo"
    READABILITY = "readability"
    TONE = "tone"
    KEYWORDS = "keywords"
    AI_REWRITE = "ai_rewrite"
    GRAMMAR = "grammar"
    SENTIMENT = "sentiment"


class ContentVersion(BaseModel):
    """Content version model for tracking changes."""
    
    version_number: int = Field(ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str  # User ID
    
    # Content data
    title: str
    content: str
    content_html: Optional[str] = None
    excerpt: Optional[str] = None
    
    # Metadata
    word_count: int = 0
    character_count: int = 0
    reading_time_minutes: float = 0.0
    
    # SEO metadata
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    
    # Scores from optimization
    optimization_scores: Dict[str, float] = Field(default_factory=dict)
    
    # Changes from previous version
    change_summary: Optional[str] = None
    diff_stats: Optional[Dict[str, Any]] = None


class ContentDocument(Document):
    """MongoDB document for content storage."""
    
    # Organization reference (tenant ID)
    org_id: Indexed(str)
    
    # PostgreSQL reference
    postgres_content_id: Indexed(str)
    
    # Basic info
    title: Indexed(str)
    slug: Indexed(str)
    content_type: ContentType
    
    # Current version
    current_version: int = 1
    published_version: Optional[int] = None
    
    # Version history
    versions: List[ContentVersion] = Field(default_factory=list)
    
    # Full-text search content
    search_content: Optional[str] = None
    
    # AI Analysis results
    ai_analysis: Dict[str, Any] = Field(default_factory=dict)
    
    # Tags and categories
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    
    # Custom metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    
    class Settings:
        name = "content"
        indexes = [
            IndexModel([("org_id", ASCENDING), ("slug", ASCENDING)], unique=True),
            IndexModel([("org_id", ASCENDING), ("content_type", ASCENDING)]),
            IndexModel([("org_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("search_content", TEXT)]),
            IndexModel("tags"),
            IndexModel("categories"),
        ]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "org_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "10 Best SEO Practices for 2024",
                "slug": "10-best-seo-practices-2024",
                "content_type": "article",
            }
        }
    )


class OptimizationSuggestion(BaseModel):
    """Individual optimization suggestion."""
    
    type: OptimizationType
    priority: str  # high, medium, low
    description: str
    
    # Location in content
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    context: Optional[str] = None
    
    # Suggested change
    original_text: Optional[str] = None
    suggested_text: Optional[str] = None
    
    # Impact
    expected_score_improvement: Optional[float] = None
    confidence: float = Field(ge=0, le=1)
    
    # Additional data
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OptimizationResult(Document):
    """MongoDB document for optimization results."""
    
    # References
    org_id: Indexed(str)
    content_id: Indexed(str)  # Reference to ContentDocument
    postgres_optimization_id: Optional[str] = None
    
    # Optimization details
    optimization_type: OptimizationType
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Model information
    model_name: str
    model_version: Optional[str] = None
    model_parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Results
    suggestions: List[OptimizationSuggestion] = Field(default_factory=list)
    
    # Scores
    before_scores: Dict[str, float] = Field(default_factory=dict)
    after_scores: Dict[str, float] = Field(default_factory=dict)
    
    # Performance metrics
    processing_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    api_cost: Optional[float] = None
    
    # Applied changes tracking
    applied_suggestions: List[str] = Field(default_factory=list)  # Suggestion IDs
    applied_at: Optional[datetime] = None
    applied_by: Optional[str] = None  # User ID
    
    class Settings:
        name = "optimization_results"
        indexes = [
            IndexModel([("org_id", ASCENDING), ("content_id", ASCENDING)]),
            IndexModel([("org_id", ASCENDING), ("optimization_type", ASCENDING)]),
            IndexModel([("org_id", ASCENDING), ("started_at", DESCENDING)]),
        ]


class AnalyticsEvent(Document):
    """MongoDB document for analytics events."""
    
    # Organization reference
    org_id: Indexed(str)
    
    # Event details
    event_type: Indexed(str)  # page_view, click, conversion, etc.
    event_name: str
    timestamp: Indexed(datetime) = Field(default_factory=datetime.utcnow)
    
    # Associated entities
    user_id: Optional[str] = None
    content_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Event data
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    
    # Geographic data
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    
    # UTM parameters
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    
    class Settings:
        name = "analytics_events"
        indexes = [
            IndexModel([("org_id", ASCENDING), ("event_type", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("org_id", ASCENDING), ("content_id", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("org_id", ASCENDING), ("user_id", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("timestamp", DESCENDING)]),  # For TTL
        ]


class ContentPerformance(Document):
    """Aggregated content performance metrics."""
    
    # References
    org_id: Indexed(str)
    content_id: Indexed(str)
    
    # Time period
    period_type: str  # hourly, daily, weekly, monthly
    period_start: Indexed(datetime)
    period_end: datetime
    
    # Metrics
    views: int = 0
    unique_views: int = 0
    average_time_on_page: float = 0.0
    bounce_rate: float = 0.0
    
    # Engagement
    clicks: int = 0
    shares: int = 0
    comments: int = 0
    likes: int = 0
    
    # Conversions
    conversions: int = 0
    conversion_rate: float = 0.0
    conversion_value: float = 0.0
    
    # SEO metrics
    organic_traffic: int = 0
    average_position: float = 0.0
    impressions: int = 0
    ctr: float = 0.0
    
    # Top sources
    top_referrers: List[Dict[str, Any]] = Field(default_factory=list)
    top_keywords: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Device breakdown
    device_breakdown: Dict[str, int] = Field(default_factory=dict)
    
    # Geographic breakdown
    country_breakdown: Dict[str, int] = Field(default_factory=dict)
    
    class Settings:
        name = "content_performance"
        indexes = [
            IndexModel([("org_id", ASCENDING), ("content_id", ASCENDING), ("period_type", ASCENDING), ("period_start", DESCENDING)]),
            IndexModel([("org_id", ASCENDING), ("period_start", DESCENDING)]),
            IndexModel([("period_start", DESCENDING)]),  # For TTL
        ]


class AIModelUsage(Document):
    """Track AI model usage for billing and optimization."""
    
    # Organization reference
    org_id: Indexed(str)
    
    # Time period
    period_type: str  # hourly, daily, monthly
    period_start: Indexed(datetime)
    period_end: datetime
    
    # Model details
    model_provider: str  # openai, anthropic, etc.
    model_name: str
    model_version: Optional[str] = None
    
    # Usage metrics
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    
    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Cost tracking
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    
    # Performance metrics
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Error tracking
    error_types: Dict[str, int] = Field(default_factory=dict)
    
    class Settings:
        name = "ai_model_usage"
        indexes = [
            IndexModel([("org_id", ASCENDING), ("period_type", ASCENDING), ("period_start", DESCENDING)]),
            IndexModel([("org_id", ASCENDING), ("model_provider", ASCENDING), ("model_name", ASCENDING)]),
            IndexModel([("period_start", DESCENDING)]),  # For TTL
        ]