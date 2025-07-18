"""
SEO analysis for content optimization.
"""

import logging
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import stopwords


logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.download('stopwords', quiet=True)
    STOP_WORDS = set(stopwords.words('english'))
except Exception as e:
    logger.warning(f"Failed to load stopwords: {e}")
    STOP_WORDS = set()


class SEOAnalysisResult(BaseModel):
    """SEO analysis results."""
    # Title analysis
    title_length: int = 0
    title_word_count: int = 0
    title_has_keywords: bool = False
    title_score: float = 0.0
    
    # Meta description
    meta_description_length: int = 0
    has_meta_description: bool = False
    meta_description_score: float = 0.0
    
    # Keyword analysis
    keyword_density: float = 0.0
    keyword_distribution: Dict[str, int] = Field(default_factory=dict)
    missing_keywords: List[str] = Field(default_factory=list)
    
    # Content structure
    heading_structure: Dict[str, int] = Field(default_factory=dict)
    has_h1: bool = False
    h1_count: int = 0
    
    # Links
    internal_links: int = 0
    external_links: int = 0
    broken_links: List[str] = Field(default_factory=list)
    
    # Images
    images_count: int = 0
    images_without_alt: int = 0
    
    # Schema markup
    has_schema_markup: bool = False
    schema_types: List[str] = Field(default_factory=list)
    
    # Overall score
    overall_score: float = 0.0
    
    # Recommendations
    seo_issues: List[Dict[str, Any]] = Field(default_factory=list)
    seo_suggestions: List[Dict[str, Any]] = Field(default_factory=list)


class SEOAnalyzer:
    """
    SEO analysis engine for content optimization.
    """
    
    # SEO best practices
    IDEAL_TITLE_LENGTH = (50, 60)
    IDEAL_META_DESC_LENGTH = (150, 160)
    IDEAL_KEYWORD_DENSITY = (1.0, 3.0)  # Percentage
    IDEAL_H1_COUNT = 1
    MIN_WORD_COUNT = 300
    
    def __init__(self):
        self.stop_words = STOP_WORDS
    
    async def analyze(
        self,
        text: str,
        title: str = "",
        meta_description: str = "",
        target_keywords: List[str] = None,
        url: Optional[str] = None
    ) -> SEOAnalysisResult:
        """
        Perform comprehensive SEO analysis.
        
        Args:
            text: Main content text
            title: Page title
            meta_description: Meta description
            target_keywords: Target keywords to check for
            url: Page URL (optional)
        
        Returns:
            SEO analysis results
        """
        target_keywords = target_keywords or []
        result = SEOAnalysisResult()
        
        # Parse HTML if provided
        soup = None
        if '<' in text and '>' in text:
            soup = BeautifulSoup(text, 'html.parser')
            # Extract text content
            clean_text = soup.get_text(separator=' ', strip=True)
        else:
            clean_text = text
        
        # Analyze title
        self._analyze_title(title, target_keywords, result)
        
        # Analyze meta description
        self._analyze_meta_description(meta_description, target_keywords, result)
        
        # Analyze keywords
        self._analyze_keywords(clean_text, target_keywords, result)
        
        # Analyze structure
        if soup:
            self._analyze_html_structure(soup, result)
        else:
            self._analyze_text_structure(text, result)
        
        # Analyze links
        if soup:
            self._analyze_links(soup, url, result)
        
        # Analyze images
        if soup:
            self._analyze_images(soup, result)
        
        # Check for schema markup
        if soup:
            self._check_schema_markup(soup, result)
        
        # Calculate overall score
        self._calculate_overall_score(result)
        
        # Generate recommendations
        self._generate_recommendations(result, len(clean_text.split()))
        
        return result
    
    def _analyze_title(
        self,
        title: str,
        keywords: List[str],
        result: SEOAnalysisResult
    ):
        """Analyze page title for SEO."""
        result.title_length = len(title)
        result.title_word_count = len(title.split())
        
        # Check for keywords in title
        title_lower = title.lower()
        result.title_has_keywords = any(
            keyword.lower() in title_lower for keyword in keywords
        )
        
        # Calculate title score
        score = 100.0
        
        # Length penalty
        if result.title_length < self.IDEAL_TITLE_LENGTH[0]:
            score -= 20
        elif result.title_length > self.IDEAL_TITLE_LENGTH[1]:
            score -= 10
        
        # Keyword bonus
        if result.title_has_keywords:
            score += 10
        else:
            score -= 30
        
        result.title_score = max(0, min(100, score))
    
    def _analyze_meta_description(
        self,
        meta_description: str,
        keywords: List[str],
        result: SEOAnalysisResult
    ):
        """Analyze meta description for SEO."""
        result.meta_description_length = len(meta_description)
        result.has_meta_description = bool(meta_description)
        
        if not meta_description:
            result.meta_description_score = 0
            return
        
        # Calculate score
        score = 100.0
        
        # Length penalty
        if result.meta_description_length < self.IDEAL_META_DESC_LENGTH[0]:
            score -= 20
        elif result.meta_description_length > self.IDEAL_META_DESC_LENGTH[1]:
            score -= 10
        
        # Keyword bonus
        desc_lower = meta_description.lower()
        has_keywords = any(
            keyword.lower() in desc_lower for keyword in keywords
        )
        if has_keywords:
            score += 10
        else:
            score -= 20
        
        result.meta_description_score = max(0, min(100, score))
    
    def _analyze_keywords(
        self,
        text: str,
        target_keywords: List[str],
        result: SEOAnalysisResult
    ):
        """Analyze keyword usage and density."""
        words = text.lower().split()
        total_words = len(words)
        
        if total_words == 0:
            return
        
        # Count keyword occurrences
        keyword_counts = {}
        for keyword in target_keywords:
            keyword_lower = keyword.lower()
            count = text.lower().count(keyword_lower)
            keyword_counts[keyword] = count
        
        result.keyword_distribution = keyword_counts
        
        # Calculate overall keyword density
        total_keyword_occurrences = sum(keyword_counts.values())
        result.keyword_density = (total_keyword_occurrences / total_words) * 100
        
        # Find missing keywords
        result.missing_keywords = [
            kw for kw, count in keyword_counts.items() if count == 0
        ]
    
    def _analyze_html_structure(self, soup: BeautifulSoup, result: SEOAnalysisResult):
        """Analyze HTML structure for SEO."""
        # Count headings
        heading_counts = {}
        for i in range(1, 7):
            headings = soup.find_all(f'h{i}')
            if headings:
                heading_counts[f'h{i}'] = len(headings)
        
        result.heading_structure = heading_counts
        result.h1_count = heading_counts.get('h1', 0)
        result.has_h1 = result.h1_count > 0
    
    def _analyze_text_structure(self, text: str, result: SEOAnalysisResult):
        """Analyze text structure when HTML is not available."""
        # Look for markdown-style headings
        h1_matches = re.findall(r'^#\s+.+$', text, re.MULTILINE)
        h2_matches = re.findall(r'^##\s+.+$', text, re.MULTILINE)
        
        if h1_matches:
            result.heading_structure['h1'] = len(h1_matches)
            result.h1_count = len(h1_matches)
            result.has_h1 = True
        
        if h2_matches:
            result.heading_structure['h2'] = len(h2_matches)
    
    def _analyze_links(
        self,
        soup: BeautifulSoup,
        base_url: Optional[str],
        result: SEOAnalysisResult
    ):
        """Analyze links in content."""
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            
            # Classify link
            if href.startswith(('http://', 'https://')):
                if base_url and urlparse(href).netloc == urlparse(base_url).netloc:
                    result.internal_links += 1
                else:
                    result.external_links += 1
            elif href.startswith(('//', 'mailto:', 'tel:')):
                result.external_links += 1
            else:
                result.internal_links += 1
    
    def _analyze_images(self, soup: BeautifulSoup, result: SEOAnalysisResult):
        """Analyze images for SEO."""
        images = soup.find_all('img')
        result.images_count = len(images)
        
        for img in images:
            if not img.get('alt'):
                result.images_without_alt += 1
    
    def _check_schema_markup(self, soup: BeautifulSoup, result: SEOAnalysisResult):
        """Check for schema.org markup."""
        # Check for JSON-LD
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        if json_ld_scripts:
            result.has_schema_markup = True
            result.schema_types.append('JSON-LD')
        
        # Check for microdata
        if soup.find_all(attrs={'itemscope': True}):
            result.has_schema_markup = True
            result.schema_types.append('Microdata')
        
        # Check for RDFa
        if soup.find_all(attrs={'typeof': True}):
            result.has_schema_markup = True
            result.schema_types.append('RDFa')
    
    def _calculate_overall_score(self, result: SEOAnalysisResult):
        """Calculate overall SEO score."""
        scores = []
        weights = []
        
        # Title score (25% weight)
        scores.append(result.title_score)
        weights.append(0.25)
        
        # Meta description score (15% weight)
        scores.append(result.meta_description_score)
        weights.append(0.15)
        
        # Keyword density score (20% weight)
        if self.IDEAL_KEYWORD_DENSITY[0] <= result.keyword_density <= self.IDEAL_KEYWORD_DENSITY[1]:
            keyword_score = 100
        elif result.keyword_density < self.IDEAL_KEYWORD_DENSITY[0]:
            keyword_score = 50
        else:
            keyword_score = 70
        scores.append(keyword_score)
        weights.append(0.20)
        
        # Structure score (20% weight)
        structure_score = 100
        if not result.has_h1:
            structure_score -= 30
        if result.h1_count > 1:
            structure_score -= 20
        scores.append(structure_score)
        weights.append(0.20)
        
        # Image optimization score (10% weight)
        if result.images_count > 0:
            image_score = 100 - (result.images_without_alt / result.images_count) * 100
        else:
            image_score = 100
        scores.append(image_score)
        weights.append(0.10)
        
        # Schema markup bonus (10% weight)
        schema_score = 100 if result.has_schema_markup else 0
        scores.append(schema_score)
        weights.append(0.10)
        
        # Calculate weighted average
        result.overall_score = sum(s * w for s, w in zip(scores, weights))
    
    def _generate_recommendations(
        self,
        result: SEOAnalysisResult,
        word_count: int
    ):
        """Generate SEO recommendations."""
        # Title recommendations
        if result.title_length < self.IDEAL_TITLE_LENGTH[0]:
            result.seo_issues.append({
                "type": "title",
                "severity": "high",
                "message": f"Title too short ({result.title_length} chars). Aim for {self.IDEAL_TITLE_LENGTH[0]}-{self.IDEAL_TITLE_LENGTH[1]} characters."
            })
        elif result.title_length > self.IDEAL_TITLE_LENGTH[1]:
            result.seo_issues.append({
                "type": "title",
                "severity": "medium",
                "message": f"Title too long ({result.title_length} chars). May be truncated in search results."
            })
        
        if not result.title_has_keywords:
            result.seo_suggestions.append({
                "type": "title",
                "priority": "high",
                "message": "Include target keywords in the title for better relevance."
            })
        
        # Meta description recommendations
        if not result.has_meta_description:
            result.seo_issues.append({
                "type": "meta_description",
                "severity": "high",
                "message": "Missing meta description. Add a compelling 150-160 character description."
            })
        elif result.meta_description_length < self.IDEAL_META_DESC_LENGTH[0]:
            result.seo_suggestions.append({
                "type": "meta_description",
                "priority": "medium",
                "message": f"Meta description too short ({result.meta_description_length} chars). Expand to {self.IDEAL_META_DESC_LENGTH[0]}-{self.IDEAL_META_DESC_LENGTH[1]} characters."
            })
        
        # Keyword recommendations
        if result.keyword_density < self.IDEAL_KEYWORD_DENSITY[0]:
            result.seo_suggestions.append({
                "type": "keywords",
                "priority": "high",
                "message": f"Keyword density too low ({result.keyword_density:.1f}%). Naturally include more target keywords."
            })
        elif result.keyword_density > self.IDEAL_KEYWORD_DENSITY[1]:
            result.seo_issues.append({
                "type": "keywords",
                "severity": "medium",
                "message": f"Keyword density too high ({result.keyword_density:.1f}%). Risk of keyword stuffing."
            })
        
        if result.missing_keywords:
            result.seo_suggestions.append({
                "type": "keywords",
                "priority": "medium",
                "message": f"Missing keywords: {', '.join(result.missing_keywords[:3])}. Consider including them naturally."
            })
        
        # Structure recommendations
        if not result.has_h1:
            result.seo_issues.append({
                "type": "structure",
                "severity": "high",
                "message": "Missing H1 heading. Add one clear H1 that includes target keywords."
            })
        elif result.h1_count > 1:
            result.seo_issues.append({
                "type": "structure",
                "severity": "medium",
                "message": f"Multiple H1 headings found ({result.h1_count}). Use only one H1 per page."
            })
        
        # Content length
        if word_count < self.MIN_WORD_COUNT:
            result.seo_suggestions.append({
                "type": "content",
                "priority": "high",
                "message": f"Content too short ({word_count} words). Aim for at least {self.MIN_WORD_COUNT} words for better SEO."
            })
        
        # Images
        if result.images_without_alt > 0:
            result.seo_issues.append({
                "type": "images",
                "severity": "medium",
                "message": f"{result.images_without_alt} images missing alt text. Add descriptive alt text for accessibility and SEO."
            })
        
        # Schema markup
        if not result.has_schema_markup:
            result.seo_suggestions.append({
                "type": "schema",
                "priority": "medium",
                "message": "No schema markup detected. Add structured data to help search engines understand your content."
            })