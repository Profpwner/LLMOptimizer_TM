"""
Main content analyzer that orchestrates different analysis engines.
"""

import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
import asyncio

from pydantic import BaseModel, Field

from .text_analyzer import TextAnalyzer, TextAnalysisResult
from .image_analyzer import ImageAnalyzer, ImageAnalysisResult
from .video_analyzer import VideoAnalyzer, VideoAnalysisResult
from .seo_analyzer import SEOAnalyzer, SEOAnalysisResult
from .quality_scorer import QualityScorer, QualityScore


logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Types of content that can be analyzed."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    CODE = "code"
    MIXED = "mixed"


class AnalysisResult(BaseModel):
    """Comprehensive analysis result for content."""
    content_id: str
    content_type: ContentType
    
    # Individual analysis results
    text_analysis: Optional[TextAnalysisResult] = None
    image_analysis: Optional[ImageAnalysisResult] = None
    video_analysis: Optional[VideoAnalysisResult] = None
    seo_analysis: Optional[SEOAnalysisResult] = None
    
    # Overall scores
    quality_score: Optional[QualityScore] = None
    
    # Metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_duration_ms: int = 0
    
    # Issues and recommendations
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Summary
    summary: Optional[str] = None
    
    def add_issue(
        self,
        category: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Add an issue to the analysis."""
        self.issues.append({
            "category": category,
            "severity": severity,
            "message": message,
            "details": details or {}
        })
    
    def add_recommendation(
        self,
        category: str,
        priority: str,
        message: str,
        action: Optional[str] = None
    ):
        """Add a recommendation to the analysis."""
        self.recommendations.append({
            "category": category,
            "priority": priority,
            "message": message,
            "action": action
        })


class ContentAnalyzer:
    """
    Main content analyzer that coordinates different analysis engines.
    """
    
    def __init__(self):
        self.text_analyzer = TextAnalyzer()
        self.image_analyzer = ImageAnalyzer()
        self.video_analyzer = VideoAnalyzer()
        self.seo_analyzer = SEOAnalyzer()
        self.quality_scorer = QualityScorer()
    
    async def analyze(
        self,
        content_id: str,
        content: Union[str, bytes, Dict[str, Any]],
        content_type: Optional[ContentType] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze content using appropriate analyzers.
        
        Args:
            content_id: Unique identifier for the content
            content: The content to analyze (text, binary data, or structured data)
            content_type: Type of content (auto-detected if not provided)
            options: Analysis options (e.g., target_audience, keywords, etc.)
        
        Returns:
            Comprehensive analysis result
        """
        start_time = datetime.utcnow()
        options = options or {}
        
        # Auto-detect content type if not provided
        if not content_type:
            content_type = self._detect_content_type(content)
        
        # Create result object
        result = AnalysisResult(
            content_id=content_id,
            content_type=content_type
        )
        
        # Run appropriate analyzers
        tasks = []
        
        if content_type in [ContentType.TEXT, ContentType.MIXED]:
            tasks.append(self._analyze_text(content, options, result))
        
        if content_type in [ContentType.IMAGE, ContentType.MIXED]:
            tasks.append(self._analyze_image(content, options, result))
        
        if content_type in [ContentType.VIDEO, ContentType.MIXED]:
            tasks.append(self._analyze_video(content, options, result))
        
        # Run analyzers in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Run SEO analysis if applicable
        if result.text_analysis:
            result.seo_analysis = await self.seo_analyzer.analyze(
                text=result.text_analysis.content,
                title=options.get("title", ""),
                meta_description=options.get("meta_description", ""),
                target_keywords=options.get("keywords", [])
            )
        
        # Calculate overall quality score
        result.quality_score = await self.quality_scorer.calculate_score(result)
        
        # Generate summary and recommendations
        self._generate_summary(result)
        self._generate_recommendations(result)
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.analysis_duration_ms = int(duration)
        
        logger.info(f"Content analysis completed for {content_id} in {duration}ms")
        
        return result
    
    async def _analyze_text(
        self,
        content: Union[str, Dict[str, Any]],
        options: Dict[str, Any],
        result: AnalysisResult
    ):
        """Analyze text content."""
        try:
            text = content if isinstance(content, str) else content.get("text", "")
            if text:
                result.text_analysis = await self.text_analyzer.analyze(
                    text,
                    language=options.get("language"),
                    target_audience=options.get("target_audience")
                )
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
            result.add_issue("text_analysis", "error", str(e))
    
    async def _analyze_image(
        self,
        content: Union[bytes, Dict[str, Any]],
        options: Dict[str, Any],
        result: AnalysisResult
    ):
        """Analyze image content."""
        try:
            if isinstance(content, dict) and "image_data" in content:
                result.image_analysis = await self.image_analyzer.analyze(
                    content["image_data"],
                    format=content.get("format", "jpeg")
                )
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            result.add_issue("image_analysis", "error", str(e))
    
    async def _analyze_video(
        self,
        content: Union[bytes, Dict[str, Any]],
        options: Dict[str, Any],
        result: AnalysisResult
    ):
        """Analyze video content."""
        try:
            if isinstance(content, dict) and "video_url" in content:
                result.video_analysis = await self.video_analyzer.analyze(
                    content["video_url"],
                    extract_audio=options.get("extract_audio", True)
                )
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            result.add_issue("video_analysis", "error", str(e))
    
    def _detect_content_type(self, content: Any) -> ContentType:
        """Auto-detect content type."""
        if isinstance(content, str):
            return ContentType.TEXT
        elif isinstance(content, bytes):
            # Simple detection based on magic bytes
            if content.startswith(b'\xff\xd8\xff'):  # JPEG
                return ContentType.IMAGE
            elif content.startswith(b'\x89PNG'):  # PNG
                return ContentType.IMAGE
            elif b'ftypmp4' in content[:20]:  # MP4
                return ContentType.VIDEO
            else:
                return ContentType.TEXT
        elif isinstance(content, dict):
            if "text" in content and "image_data" in content:
                return ContentType.MIXED
            elif "text" in content:
                return ContentType.TEXT
            elif "image_data" in content:
                return ContentType.IMAGE
            elif "video_url" in content:
                return ContentType.VIDEO
        
        return ContentType.TEXT  # Default
    
    def _generate_summary(self, result: AnalysisResult):
        """Generate analysis summary."""
        summaries = []
        
        if result.text_analysis:
            summaries.append(
                f"Text: {result.text_analysis.word_count} words, "
                f"readability grade {result.text_analysis.readability.flesch_kincaid_grade:.1f}"
            )
        
        if result.seo_analysis:
            summaries.append(
                f"SEO: score {result.seo_analysis.overall_score:.0f}/100"
            )
        
        if result.quality_score:
            summaries.append(
                f"Quality: {result.quality_score.overall_score:.0f}/100"
            )
        
        result.summary = " | ".join(summaries)
    
    def _generate_recommendations(self, result: AnalysisResult):
        """Generate recommendations based on analysis."""
        # Text recommendations
        if result.text_analysis:
            if result.text_analysis.readability.flesch_kincaid_grade > 12:
                result.add_recommendation(
                    "readability",
                    "high",
                    "Content is too complex. Consider simplifying sentences and using shorter words.",
                    "simplify_text"
                )
            
            if result.text_analysis.sentiment.polarity < -0.3:
                result.add_recommendation(
                    "sentiment",
                    "medium",
                    "Content has negative sentiment. Consider adding more positive language.",
                    "improve_sentiment"
                )
        
        # SEO recommendations
        if result.seo_analysis:
            if result.seo_analysis.keyword_density < 0.5:
                result.add_recommendation(
                    "seo",
                    "high",
                    "Keyword density is too low. Include target keywords more naturally.",
                    "increase_keywords"
                )
            
            if not result.seo_analysis.has_meta_description:
                result.add_recommendation(
                    "seo",
                    "high",
                    "Missing meta description. Add a compelling 150-160 character description.",
                    "add_meta_description"
                )
        
        # Quality recommendations
        if result.quality_score and result.quality_score.overall_score < 70:
            result.add_recommendation(
                "quality",
                "high",
                f"Overall quality score is low ({result.quality_score.overall_score:.0f}/100). "
                "Focus on improving content structure, readability, and SEO.",
                "improve_quality"
            )