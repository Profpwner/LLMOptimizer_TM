"""
Text content analysis including readability, sentiment, and language processing.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import asyncio

from pydantic import BaseModel, Field
import textstat
from langdetect import detect, LangDetectException
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize, sent_tokenize
import yake


logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('vader_lexicon', quiet=True)
    nltk.download('stopwords', quiet=True)
except Exception as e:
    logger.warning(f"Failed to download NLTK data: {e}")


class ReadabilityMetrics(BaseModel):
    """Readability metrics for text content."""
    flesch_reading_ease: float = Field(..., description="0-100, higher is easier")
    flesch_kincaid_grade: float = Field(..., description="US grade level")
    gunning_fog: float = Field(..., description="Years of education needed")
    smog_index: float = Field(..., description="Years of education needed")
    automated_readability_index: float
    coleman_liau_index: float
    linsear_write_formula: float
    dale_chall_readability_score: float
    
    @property
    def average_grade_level(self) -> float:
        """Calculate average grade level across metrics."""
        grades = [
            self.flesch_kincaid_grade,
            self.gunning_fog,
            self.smog_index,
            self.automated_readability_index,
            self.coleman_liau_index
        ]
        return sum(grades) / len(grades)


class SentimentAnalysis(BaseModel):
    """Sentiment analysis results."""
    polarity: float = Field(..., description="Overall sentiment (-1 to 1)")
    subjectivity: float = Field(..., description="Subjectivity (0 to 1)")
    compound: float = Field(..., description="VADER compound score")
    positive: float = Field(..., description="Positive sentiment ratio")
    negative: float = Field(..., description="Negative sentiment ratio")
    neutral: float = Field(..., description="Neutral sentiment ratio")


class KeywordExtraction(BaseModel):
    """Extracted keywords and phrases."""
    keywords: List[Dict[str, Any]] = Field(default_factory=list)
    top_words: List[str] = Field(default_factory=list)
    key_phrases: List[str] = Field(default_factory=list)


class TextStatistics(BaseModel):
    """Basic text statistics."""
    character_count: int = 0
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    average_word_length: float = 0
    average_sentence_length: float = 0
    lexical_diversity: float = 0  # Unique words / total words


class TextAnalysisResult(BaseModel):
    """Complete text analysis result."""
    content: str
    language: str
    statistics: TextStatistics
    readability: ReadabilityMetrics
    sentiment: SentimentAnalysis
    keywords: KeywordExtraction
    
    # Content quality indicators
    has_spelling_errors: bool = False
    grammar_score: float = Field(default=100.0, ge=0, le=100)
    
    # Structure analysis
    has_headings: bool = False
    has_lists: bool = False
    has_images: bool = False
    
    # Additional metadata
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class TextAnalyzer:
    """
    Comprehensive text content analyzer.
    """
    
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.keyword_extractor = yake.KeywordExtractor(
            lan="en",
            n=3,  # Max n-gram size
            dedupLim=0.7,
            top=20
        )
    
    async def analyze(
        self,
        text: str,
        language: Optional[str] = None,
        target_audience: Optional[str] = None
    ) -> TextAnalysisResult:
        """
        Perform comprehensive text analysis.
        
        Args:
            text: Text content to analyze
            language: Language code (auto-detected if not provided)
            target_audience: Target audience for readability assessment
        
        Returns:
            Complete text analysis result
        """
        # Detect language if not provided
        if not language:
            try:
                language = detect(text)
            except LangDetectException:
                language = "en"  # Default to English
        
        # Run analyses in parallel
        statistics_task = asyncio.create_task(self._calculate_statistics(text))
        readability_task = asyncio.create_task(self._calculate_readability(text))
        sentiment_task = asyncio.create_task(self._analyze_sentiment(text))
        keywords_task = asyncio.create_task(self._extract_keywords(text, language))
        structure_task = asyncio.create_task(self._analyze_structure(text))
        
        # Wait for all tasks
        statistics, readability, sentiment, keywords, structure = await asyncio.gather(
            statistics_task,
            readability_task,
            sentiment_task,
            keywords_task,
            structure_task
        )
        
        return TextAnalysisResult(
            content=text,
            language=language,
            statistics=statistics,
            readability=readability,
            sentiment=sentiment,
            keywords=keywords,
            has_headings=structure["has_headings"],
            has_lists=structure["has_lists"],
            has_images=structure["has_images"]
        )
    
    async def _calculate_statistics(self, text: str) -> TextStatistics:
        """Calculate basic text statistics."""
        # Clean text for analysis
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        # Tokenize
        try:
            words = word_tokenize(clean_text)
            sentences = sent_tokenize(clean_text)
        except Exception:
            # Fallback to simple splitting
            words = clean_text.split()
            sentences = clean_text.split('.')
        
        # Count paragraphs
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        # Calculate statistics
        word_count = len(words)
        unique_words = set(w.lower() for w in words if w.isalnum())
        
        return TextStatistics(
            character_count=len(text),
            word_count=word_count,
            sentence_count=len(sentences),
            paragraph_count=len(paragraphs),
            average_word_length=sum(len(w) for w in words) / word_count if word_count > 0 else 0,
            average_sentence_length=word_count / len(sentences) if sentences else 0,
            lexical_diversity=len(unique_words) / word_count if word_count > 0 else 0
        )
    
    async def _calculate_readability(self, text: str) -> ReadabilityMetrics:
        """Calculate readability metrics."""
        try:
            return ReadabilityMetrics(
                flesch_reading_ease=textstat.flesch_reading_ease(text),
                flesch_kincaid_grade=textstat.flesch_kincaid_grade(text),
                gunning_fog=textstat.gunning_fog(text),
                smog_index=textstat.smog_index(text),
                automated_readability_index=textstat.automated_readability_index(text),
                coleman_liau_index=textstat.coleman_liau_index(text),
                linsear_write_formula=textstat.linsear_write_formula(text),
                dale_chall_readability_score=textstat.dale_chall_readability_score(text)
            )
        except Exception as e:
            logger.error(f"Readability calculation failed: {e}")
            # Return default values
            return ReadabilityMetrics(
                flesch_reading_ease=50.0,
                flesch_kincaid_grade=10.0,
                gunning_fog=10.0,
                smog_index=10.0,
                automated_readability_index=10.0,
                coleman_liau_index=10.0,
                linsear_write_formula=10.0,
                dale_chall_readability_score=10.0
            )
    
    async def _analyze_sentiment(self, text: str) -> SentimentAnalysis:
        """Analyze text sentiment."""
        # VADER sentiment scores
        scores = self.sia.polarity_scores(text)
        
        # Calculate overall polarity
        polarity = scores['compound']
        
        # Estimate subjectivity (simplified - in production use TextBlob or similar)
        opinion_words = ['think', 'believe', 'feel', 'opinion', 'seems', 'appears']
        word_count = len(text.split())
        opinion_count = sum(1 for word in opinion_words if word in text.lower())
        subjectivity = min(opinion_count / word_count, 1.0) if word_count > 0 else 0
        
        return SentimentAnalysis(
            polarity=polarity,
            subjectivity=subjectivity,
            compound=scores['compound'],
            positive=scores['pos'],
            negative=scores['neg'],
            neutral=scores['neu']
        )
    
    async def _extract_keywords(self, text: str, language: str) -> KeywordExtraction:
        """Extract keywords and key phrases."""
        try:
            # Update extractor language if needed
            if language != "en":
                self.keyword_extractor = yake.KeywordExtractor(
                    lan=language,
                    n=3,
                    dedupLim=0.7,
                    top=20
                )
            
            # Extract keywords
            keywords = self.keyword_extractor.extract_keywords(text)
            
            # Format results
            keyword_list = [
                {"keyword": kw[0], "score": kw[1]}
                for kw in keywords
            ]
            
            # Get top single words and phrases
            top_words = [kw["keyword"] for kw in keyword_list if ' ' not in kw["keyword"]][:10]
            key_phrases = [kw["keyword"] for kw in keyword_list if ' ' in kw["keyword"]][:10]
            
            return KeywordExtraction(
                keywords=keyword_list,
                top_words=top_words,
                key_phrases=key_phrases
            )
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            return KeywordExtraction()
    
    async def _analyze_structure(self, text: str) -> Dict[str, bool]:
        """Analyze text structure."""
        # Check for common structural elements
        has_headings = bool(re.search(r'^#{1,6}\s+.+|^.+\n[=-]+$', text, re.MULTILINE))
        has_lists = bool(re.search(r'^\s*[-*+•]\s+.+|^\s*\d+\.\s+.+', text, re.MULTILINE))
        has_images = bool(re.search(r'!\[.*?\]\(.*?\)|<img\s+.*?>', text, re.IGNORECASE))
        
        return {
            "has_headings": has_headings,
            "has_lists": has_lists,
            "has_images": has_images
        }