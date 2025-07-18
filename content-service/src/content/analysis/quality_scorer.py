"""
Content quality scoring system.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

from .analyzer import AnalysisResult


logger = logging.getLogger(__name__)


class QualityDimension(BaseModel):
    """Individual quality dimension score."""
    name: str
    score: float = Field(..., ge=0, le=100)
    weight: float = Field(default=1.0, ge=0, le=1.0)
    factors: Dict[str, float] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)


class QualityScore(BaseModel):
    """Overall content quality score."""
    overall_score: float = Field(..., ge=0, le=100)
    
    # Individual dimensions
    readability_score: float = Field(..., ge=0, le=100)
    relevance_score: float = Field(..., ge=0, le=100)
    completeness_score: float = Field(..., ge=0, le=100)
    accuracy_score: float = Field(..., ge=0, le=100)
    engagement_score: float = Field(..., ge=0, le=100)
    seo_score: float = Field(..., ge=0, le=100)
    accessibility_score: float = Field(..., ge=0, le=100)
    
    # Detailed dimensions
    dimensions: List[QualityDimension] = Field(default_factory=list)
    
    # Quality grade
    grade: str = Field(default="F")
    
    # Metadata
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_grade(self) -> str:
        """Get letter grade based on score."""
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        else:
            return "F"


class QualityScorer:
    """
    Calculate comprehensive content quality scores.
    """
    
    # Quality thresholds
    READABILITY_THRESHOLDS = {
        "optimal_grade": (6, 10),  # Target grade level
        "optimal_ease": (60, 80),  # Flesch reading ease
    }
    
    CONTENT_THRESHOLDS = {
        "min_word_count": 300,
        "optimal_word_count": (600, 1500),
        "min_paragraph_count": 3,
        "optimal_sentences_per_paragraph": (3, 7),
    }
    
    async def calculate_score(self, analysis: AnalysisResult) -> QualityScore:
        """
        Calculate comprehensive quality score from analysis results.
        
        Args:
            analysis: Complete content analysis result
        
        Returns:
            Quality score with detailed breakdown
        """
        dimensions = []
        
        # Calculate readability score
        readability_dim = self._calculate_readability_score(analysis)
        dimensions.append(readability_dim)
        
        # Calculate relevance score
        relevance_dim = self._calculate_relevance_score(analysis)
        dimensions.append(relevance_dim)
        
        # Calculate completeness score
        completeness_dim = self._calculate_completeness_score(analysis)
        dimensions.append(completeness_dim)
        
        # Calculate accuracy score
        accuracy_dim = self._calculate_accuracy_score(analysis)
        dimensions.append(accuracy_dim)
        
        # Calculate engagement score
        engagement_dim = self._calculate_engagement_score(analysis)
        dimensions.append(engagement_dim)
        
        # Calculate SEO score
        seo_dim = self._calculate_seo_score(analysis)
        dimensions.append(seo_dim)
        
        # Calculate accessibility score
        accessibility_dim = self._calculate_accessibility_score(analysis)
        dimensions.append(accessibility_dim)
        
        # Calculate overall score
        total_weight = sum(dim.weight for dim in dimensions)
        overall_score = sum(
            dim.score * dim.weight for dim in dimensions
        ) / total_weight if total_weight > 0 else 0
        
        quality_score = QualityScore(
            overall_score=overall_score,
            readability_score=readability_dim.score,
            relevance_score=relevance_dim.score,
            completeness_score=completeness_dim.score,
            accuracy_score=accuracy_dim.score,
            engagement_score=engagement_dim.score,
            seo_score=seo_dim.score,
            accessibility_score=accessibility_dim.score,
            dimensions=dimensions
        )
        
        quality_score.grade = quality_score.get_grade()
        
        return quality_score
    
    def _calculate_readability_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate readability quality score."""
        dimension = QualityDimension(
            name="Readability",
            weight=0.20
        )
        
        if not analysis.text_analysis:
            dimension.score = 50
            dimension.issues.append("No text analysis available")
            return dimension
        
        readability = analysis.text_analysis.readability
        factors = {}
        
        # Grade level score (40% of readability)
        grade = readability.average_grade_level
        optimal_min, optimal_max = self.READABILITY_THRESHOLDS["optimal_grade"]
        
        if optimal_min <= grade <= optimal_max:
            grade_score = 100
        elif grade < optimal_min:
            grade_score = 80 - (optimal_min - grade) * 10
        else:
            grade_score = 80 - (grade - optimal_max) * 5
        
        factors["grade_level"] = max(0, min(100, grade_score))
        
        # Reading ease score (40% of readability)
        ease = readability.flesch_reading_ease
        ease_min, ease_max = self.READABILITY_THRESHOLDS["optimal_ease"]
        
        if ease_min <= ease <= ease_max:
            ease_score = 100
        elif ease < ease_min:
            ease_score = 70 + (ease / ease_min) * 30
        else:
            ease_score = 70 + ((100 - ease) / (100 - ease_max)) * 30
        
        factors["reading_ease"] = max(0, min(100, ease_score))
        
        # Sentence length score (20% of readability)
        avg_sentence_length = analysis.text_analysis.statistics.average_sentence_length
        if 15 <= avg_sentence_length <= 20:
            sentence_score = 100
        elif avg_sentence_length < 15:
            sentence_score = 80
        else:
            sentence_score = max(0, 100 - (avg_sentence_length - 20) * 2)
        
        factors["sentence_length"] = sentence_score
        
        # Calculate weighted readability score
        dimension.score = (
            factors["grade_level"] * 0.4 +
            factors["reading_ease"] * 0.4 +
            factors["sentence_length"] * 0.2
        )
        
        dimension.factors = factors
        
        # Add issues
        if grade > optimal_max:
            dimension.issues.append(f"Content too complex (grade {grade:.1f})")
        elif grade < optimal_min:
            dimension.issues.append(f"Content too simple (grade {grade:.1f})")
        
        if ease < ease_min:
            dimension.issues.append("Low reading ease score")
        
        return dimension
    
    def _calculate_relevance_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate content relevance score."""
        dimension = QualityDimension(
            name="Relevance",
            weight=0.15
        )
        
        factors = {}
        
        # Keyword relevance (60% of relevance)
        if analysis.seo_analysis:
            keyword_density = analysis.seo_analysis.keyword_density
            if 1.0 <= keyword_density <= 3.0:
                keyword_score = 100
            elif keyword_density < 1.0:
                keyword_score = keyword_density * 100
            else:
                keyword_score = max(0, 100 - (keyword_density - 3.0) * 20)
            
            factors["keyword_relevance"] = keyword_score
            
            # Missing keywords penalty
            missing_count = len(analysis.seo_analysis.missing_keywords)
            if missing_count > 0:
                factors["keyword_coverage"] = max(0, 100 - missing_count * 20)
            else:
                factors["keyword_coverage"] = 100
        else:
            factors["keyword_relevance"] = 50
            factors["keyword_coverage"] = 50
        
        # Topic focus (40% of relevance)
        if analysis.text_analysis and analysis.text_analysis.keywords.keywords:
            # Check keyword concentration
            top_keywords = analysis.text_analysis.keywords.keywords[:5]
            if top_keywords:
                avg_score = sum(kw["score"] for kw in top_keywords) / len(top_keywords)
                topic_focus_score = min(100, (1 - avg_score) * 200)  # YAKE scores are inverted
            else:
                topic_focus_score = 50
        else:
            topic_focus_score = 50
        
        factors["topic_focus"] = topic_focus_score
        
        # Calculate weighted relevance score
        dimension.score = (
            factors.get("keyword_relevance", 50) * 0.3 +
            factors.get("keyword_coverage", 50) * 0.3 +
            factors.get("topic_focus", 50) * 0.4
        )
        
        dimension.factors = factors
        
        return dimension
    
    def _calculate_completeness_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate content completeness score."""
        dimension = QualityDimension(
            name="Completeness",
            weight=0.15
        )
        
        factors = {}
        
        if analysis.text_analysis:
            stats = analysis.text_analysis.statistics
            
            # Word count score (40% of completeness)
            word_count = stats.word_count
            min_words = self.CONTENT_THRESHOLDS["min_word_count"]
            optimal_min, optimal_max = self.CONTENT_THRESHOLDS["optimal_word_count"]
            
            if optimal_min <= word_count <= optimal_max:
                word_score = 100
            elif word_count < min_words:
                word_score = (word_count / min_words) * 50
            elif word_count < optimal_min:
                word_score = 50 + ((word_count - min_words) / (optimal_min - min_words)) * 50
            else:
                word_score = max(70, 100 - ((word_count - optimal_max) / optimal_max) * 30)
            
            factors["word_count"] = word_score
            
            # Structure score (30% of completeness)
            structure_score = 0
            if analysis.text_analysis.has_headings:
                structure_score += 40
            if analysis.text_analysis.has_lists:
                structure_score += 30
            if stats.paragraph_count >= self.CONTENT_THRESHOLDS["min_paragraph_count"]:
                structure_score += 30
            
            factors["structure"] = structure_score
            
            # Media inclusion (30% of completeness)
            media_score = 0
            if analysis.text_analysis.has_images:
                media_score += 50
            if analysis.image_analysis:
                media_score += 50
            elif analysis.video_analysis:
                media_score = 100
            
            factors["media_inclusion"] = media_score
        else:
            factors = {
                "word_count": 50,
                "structure": 50,
                "media_inclusion": 0
            }
        
        # Calculate weighted completeness score
        dimension.score = (
            factors["word_count"] * 0.4 +
            factors["structure"] * 0.3 +
            factors["media_inclusion"] * 0.3
        )
        
        dimension.factors = factors
        
        # Add issues
        if analysis.text_analysis:
            if analysis.text_analysis.statistics.word_count < self.CONTENT_THRESHOLDS["min_word_count"]:
                dimension.issues.append("Content too short")
            if not analysis.text_analysis.has_headings:
                dimension.issues.append("No headings found")
        
        return dimension
    
    def _calculate_accuracy_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate content accuracy score."""
        dimension = QualityDimension(
            name="Accuracy",
            weight=0.15
        )
        
        # Start with a base score
        base_score = 85
        
        factors = {
            "grammar": 100,  # Assume good grammar unless detected otherwise
            "spelling": 100,  # Assume good spelling unless detected otherwise
            "facts": 90,     # Assume mostly accurate unless fact-checked
        }
        
        # Deduct points for issues
        if analysis.issues:
            for issue in analysis.issues:
                if issue["category"] == "text_analysis" and issue["severity"] == "error":
                    base_score -= 10
        
        # If grammar score is available from text analysis
        if analysis.text_analysis and hasattr(analysis.text_analysis, 'grammar_score'):
            factors["grammar"] = analysis.text_analysis.grammar_score
        
        dimension.score = min(100, base_score)
        dimension.factors = factors
        
        return dimension
    
    def _calculate_engagement_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate content engagement score."""
        dimension = QualityDimension(
            name="Engagement",
            weight=0.10
        )
        
        factors = {}
        
        if analysis.text_analysis:
            # Sentiment score (40% of engagement)
            sentiment = analysis.text_analysis.sentiment
            
            # Slightly positive sentiment is ideal for engagement
            if 0.1 <= sentiment.polarity <= 0.5:
                sentiment_score = 100
            elif sentiment.polarity < 0:
                sentiment_score = 50 + (sentiment.polarity + 1) * 50
            elif sentiment.polarity > 0.5:
                sentiment_score = 100 - (sentiment.polarity - 0.5) * 40
            else:
                sentiment_score = 80  # Neutral
            
            factors["sentiment"] = sentiment_score
            
            # Lexical diversity (30% of engagement)
            diversity = analysis.text_analysis.statistics.lexical_diversity
            diversity_score = min(100, diversity * 150)  # 0.67 diversity = 100 score
            factors["lexical_diversity"] = diversity_score
            
            # Structure variety (30% of engagement)
            variety_score = 0
            if analysis.text_analysis.has_headings:
                variety_score += 33
            if analysis.text_analysis.has_lists:
                variety_score += 33
            if analysis.text_analysis.has_images:
                variety_score += 34
            
            factors["structure_variety"] = variety_score
        else:
            factors = {
                "sentiment": 50,
                "lexical_diversity": 50,
                "structure_variety": 0
            }
        
        # Calculate weighted engagement score
        dimension.score = (
            factors["sentiment"] * 0.4 +
            factors["lexical_diversity"] * 0.3 +
            factors["structure_variety"] * 0.3
        )
        
        dimension.factors = factors
        
        return dimension
    
    def _calculate_seo_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate SEO quality score."""
        dimension = QualityDimension(
            name="SEO",
            weight=0.15
        )
        
        if analysis.seo_analysis:
            dimension.score = analysis.seo_analysis.overall_score
            
            # Copy SEO factors
            dimension.factors = {
                "title": analysis.seo_analysis.title_score,
                "meta_description": analysis.seo_analysis.meta_description_score,
                "keywords": min(100, analysis.seo_analysis.keyword_density * 33),
                "structure": 100 if analysis.seo_analysis.has_h1 else 50
            }
            
            # Add SEO issues
            for issue in analysis.seo_analysis.seo_issues:
                dimension.issues.append(issue["message"])
        else:
            dimension.score = 50
            dimension.factors = {"overall": 50}
            dimension.issues.append("No SEO analysis available")
        
        return dimension
    
    def _calculate_accessibility_score(self, analysis: AnalysisResult) -> QualityDimension:
        """Calculate accessibility score."""
        dimension = QualityDimension(
            name="Accessibility",
            weight=0.10
        )
        
        factors = {}
        base_score = 100
        
        # Check image accessibility
        if analysis.seo_analysis and analysis.seo_analysis.images_count > 0:
            alt_text_ratio = 1 - (
                analysis.seo_analysis.images_without_alt / 
                analysis.seo_analysis.images_count
            )
            factors["image_accessibility"] = alt_text_ratio * 100
            
            if analysis.seo_analysis.images_without_alt > 0:
                dimension.issues.append(
                    f"{analysis.seo_analysis.images_without_alt} images missing alt text"
                )
        else:
            factors["image_accessibility"] = 100
        
        # Check readability for accessibility
        if analysis.text_analysis:
            grade = analysis.text_analysis.readability.average_grade_level
            if grade <= 9:  # 9th grade or lower is accessible
                factors["readability_accessibility"] = 100
            else:
                factors["readability_accessibility"] = max(0, 100 - (grade - 9) * 10)
        else:
            factors["readability_accessibility"] = 70
        
        # Check structure for accessibility
        if analysis.text_analysis:
            structure_score = 0
            if analysis.text_analysis.has_headings:
                structure_score += 50
            if analysis.seo_analysis and analysis.seo_analysis.has_h1:
                structure_score += 50
            factors["structure_accessibility"] = structure_score
        else:
            factors["structure_accessibility"] = 50
        
        # Calculate weighted accessibility score
        dimension.score = (
            factors.get("image_accessibility", 100) * 0.33 +
            factors.get("readability_accessibility", 70) * 0.33 +
            factors.get("structure_accessibility", 50) * 0.34
        )
        
        dimension.factors = factors
        
        return dimension