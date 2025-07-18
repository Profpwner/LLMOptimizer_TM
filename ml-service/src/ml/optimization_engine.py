"""
Optimization Suggestions Engine
Generates content improvement recommendations based on semantic analysis
"""

import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from textstat import flesch_reading_ease, flesch_kincaid_grade
import re
from transformers import pipeline

logger = logging.getLogger(__name__)


@dataclass
class OptimizationSuggestion:
    """Represents an optimization suggestion"""
    suggestion_id: str
    category: str  # content, structure, keywords, readability, engagement
    priority: str  # high, medium, low
    description: str
    implementation: str
    expected_impact: Dict[str, float]
    confidence: float
    evidence: Dict[str, Any]


@dataclass
class OptimizationConfig:
    """Configuration for optimization engine"""
    target_reading_level: int = 8  # Grade level
    min_sentence_length: int = 10
    max_sentence_length: int = 25
    keyword_density: float = 0.02  # 2%
    engagement_factors: List[str] = None
    brand_voice: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.engagement_factors is None:
            self.engagement_factors = ["questions", "examples", "visuals", "cta"]


class OptimizationEngine:
    """Engine for generating content optimization suggestions"""
    
    def __init__(self, model_manager, similarity_engine, gap_analysis_engine):
        self.model_manager = model_manager
        self.similarity_engine = similarity_engine
        self.gap_analysis_engine = gap_analysis_engine
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialize_resources()
    
    def _initialize_resources(self):
        """Initialize NLP resources"""
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        try:
            nltk.data.find('averaged_perceptron_tagger')
        except LookupError:
            nltk.download('averaged_perceptron_tagger')
    
    async def generate_optimizations(
        self,
        content: str,
        metadata: Dict[str, Any],
        target_keywords: List[str],
        competitive_content: Optional[List[str]] = None,
        config: Optional[OptimizationConfig] = None
    ) -> List[OptimizationSuggestion]:
        """Generate comprehensive optimization suggestions"""
        if config is None:
            config = OptimizationConfig()
        
        logger.info("Generating optimization suggestions")
        
        # Run multiple analysis tasks in parallel
        tasks = [
            self._analyze_readability(content, config),
            self._analyze_structure(content, config),
            self._analyze_keywords(content, target_keywords, config),
            self._analyze_engagement(content, config),
            self._analyze_semantic_coherence(content),
        ]
        
        if competitive_content:
            tasks.append(self._analyze_competitive_position(content, competitive_content))
        
        results = await asyncio.gather(*tasks)
        
        # Combine all suggestions
        all_suggestions = []
        for result in results:
            all_suggestions.extend(result)
        
        # Prioritize suggestions
        all_suggestions = self._prioritize_suggestions(all_suggestions)
        
        logger.info(f"Generated {len(all_suggestions)} optimization suggestions")
        return all_suggestions
    
    async def _analyze_readability(
        self,
        content: str,
        config: OptimizationConfig
    ) -> List[OptimizationSuggestion]:
        """Analyze content readability"""
        suggestions = []
        
        # Calculate readability metrics
        reading_ease = flesch_reading_ease(content)
        grade_level = flesch_kincaid_grade(content)
        
        # Analyze sentences
        sentences = sent_tokenize(content)
        sentence_lengths = [len(word_tokenize(sent)) for sent in sentences]
        avg_sentence_length = np.mean(sentence_lengths)
        
        # Check reading level
        if grade_level > config.target_reading_level:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="read_1",
                category="readability",
                priority="high",
                description=f"Content reading level (grade {grade_level:.1f}) exceeds target ({config.target_reading_level})",
                implementation="Simplify complex sentences and use more common words",
                expected_impact={"readability": 0.3, "engagement": 0.2},
                confidence=0.9,
                evidence={
                    "current_grade": grade_level,
                    "target_grade": config.target_reading_level,
                    "reading_ease": reading_ease
                }
            ))
        
        # Check sentence length variation
        if np.std(sentence_lengths) < 5:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="read_2",
                category="readability",
                priority="medium",
                description="Low sentence length variation reduces reading flow",
                implementation="Vary sentence lengths between short (10-15 words) and medium (15-25 words) sentences",
                expected_impact={"readability": 0.2, "engagement": 0.15},
                confidence=0.8,
                evidence={
                    "avg_length": avg_sentence_length,
                    "std_dev": np.std(sentence_lengths)
                }
            ))
        
        # Find complex sentences
        complex_sentences = []
        for i, (sent, length) in enumerate(zip(sentences, sentence_lengths)):
            if length > config.max_sentence_length:
                complex_sentences.append({
                    "index": i,
                    "sentence": sent[:100] + "...",
                    "length": length
                })
        
        if complex_sentences:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="read_3",
                category="readability",
                priority="medium",
                description=f"Found {len(complex_sentences)} overly complex sentences",
                implementation="Break down complex sentences into simpler ones",
                expected_impact={"readability": 0.25, "comprehension": 0.3},
                confidence=0.85,
                evidence={"complex_sentences": complex_sentences[:3]}
            ))
        
        return suggestions
    
    async def _analyze_structure(
        self,
        content: str,
        config: OptimizationConfig
    ) -> List[OptimizationSuggestion]:
        """Analyze content structure"""
        suggestions = []
        
        # Check for headers
        header_pattern = r'^#+\s+.+|^.+\n[=-]+$'
        headers = re.findall(header_pattern, content, re.MULTILINE)
        
        if len(headers) < 3:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="struct_1",
                category="structure",
                priority="high",
                description="Insufficient headers for content organization",
                implementation="Add descriptive headers every 200-300 words to improve scannability",
                expected_impact={"readability": 0.3, "seo": 0.25},
                confidence=0.9,
                evidence={"header_count": len(headers)}
            ))
        
        # Check paragraph length
        paragraphs = content.split('\n\n')
        para_lengths = [len(word_tokenize(para)) for para in paragraphs if para.strip()]
        
        long_paragraphs = sum(1 for length in para_lengths if length > 150)
        if long_paragraphs > len(paragraphs) * 0.3:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="struct_2",
                category="structure",
                priority="medium",
                description="Many paragraphs are too long for easy reading",
                implementation="Break long paragraphs into 3-5 sentence chunks",
                expected_impact={"readability": 0.2, "engagement": 0.15},
                confidence=0.85,
                evidence={
                    "long_paragraphs": long_paragraphs,
                    "total_paragraphs": len(paragraphs)
                }
            ))
        
        # Check for lists
        list_pattern = r'^\s*[-*•]\s+.+|^\s*\d+\.\s+.+'
        lists = re.findall(list_pattern, content, re.MULTILINE)
        
        if len(lists) < 2 and len(content) > 1000:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="struct_3",
                category="structure",
                priority="medium",
                description="Content lacks bulleted or numbered lists",
                implementation="Convert key points into bulleted lists for better scannability",
                expected_impact={"readability": 0.2, "engagement": 0.2},
                confidence=0.8,
                evidence={"list_count": len(lists)}
            ))
        
        return suggestions
    
    async def _analyze_keywords(
        self,
        content: str,
        target_keywords: List[str],
        config: OptimizationConfig
    ) -> List[OptimizationSuggestion]:
        """Analyze keyword optimization"""
        suggestions = []
        
        content_lower = content.lower()
        word_count = len(word_tokenize(content))
        
        # Analyze keyword presence and density
        keyword_stats = {}
        for keyword in target_keywords:
            count = content_lower.count(keyword.lower())
            density = count / word_count if word_count > 0 else 0
            keyword_stats[keyword] = {
                "count": count,
                "density": density
            }
        
        # Check for missing keywords
        missing_keywords = [kw for kw, stats in keyword_stats.items() if stats["count"] == 0]
        if missing_keywords:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="kw_1",
                category="keywords",
                priority="high",
                description=f"Missing target keywords: {', '.join(missing_keywords[:3])}",
                implementation="Naturally incorporate missing keywords into the content",
                expected_impact={"seo": 0.4, "relevance": 0.3},
                confidence=0.95,
                evidence={"missing_keywords": missing_keywords}
            ))
        
        # Check keyword density
        for keyword, stats in keyword_stats.items():
            if stats["count"] > 0:
                if stats["density"] < config.keyword_density * 0.5:
                    suggestions.append(OptimizationSuggestion(
                        suggestion_id=f"kw_2_{keyword}",
                        category="keywords",
                        priority="medium",
                        description=f"Low density for keyword '{keyword}'",
                        implementation=f"Increase usage of '{keyword}' to 2-3% density",
                        expected_impact={"seo": 0.2},
                        confidence=0.8,
                        evidence={
                            "keyword": keyword,
                            "current_density": stats["density"],
                            "target_density": config.keyword_density
                        }
                    ))
                elif stats["density"] > config.keyword_density * 2:
                    suggestions.append(OptimizationSuggestion(
                        suggestion_id=f"kw_3_{keyword}",
                        category="keywords",
                        priority="high",
                        description=f"Keyword stuffing detected for '{keyword}'",
                        implementation=f"Reduce usage of '{keyword}' and use synonyms",
                        expected_impact={"seo": -0.3, "readability": 0.2},
                        confidence=0.9,
                        evidence={
                            "keyword": keyword,
                            "current_density": stats["density"]
                        }
                    ))
        
        # Suggest LSI keywords
        lsi_suggestions = await self._generate_lsi_keywords(content, target_keywords)
        if lsi_suggestions:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="kw_4",
                category="keywords",
                priority="medium",
                description="Add LSI (semantically related) keywords",
                implementation=f"Include related terms: {', '.join(lsi_suggestions[:5])}",
                expected_impact={"seo": 0.25, "relevance": 0.2},
                confidence=0.75,
                evidence={"lsi_keywords": lsi_suggestions}
            ))
        
        return suggestions
    
    async def _analyze_engagement(
        self,
        content: str,
        config: OptimizationConfig
    ) -> List[OptimizationSuggestion]:
        """Analyze engagement factors"""
        suggestions = []
        
        # Check for questions
        questions = re.findall(r'[^.!?]*\?', content)
        if len(questions) < 2:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="eng_1",
                category="engagement",
                priority="medium",
                description="Content lacks engaging questions",
                implementation="Add 2-3 thought-provoking questions to engage readers",
                expected_impact={"engagement": 0.25, "time_on_page": 0.2},
                confidence=0.8,
                evidence={"question_count": len(questions)}
            ))
        
        # Check for examples
        example_patterns = [
            r'for example',
            r'for instance',
            r'such as',
            r'e\.g\.',
            r'case study',
            r'example:'
        ]
        example_count = sum(len(re.findall(pattern, content, re.IGNORECASE)) 
                           for pattern in example_patterns)
        
        if example_count < 2:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="eng_2",
                category="engagement",
                priority="medium",
                description="Content lacks concrete examples",
                implementation="Add 2-3 real-world examples or case studies",
                expected_impact={"engagement": 0.3, "comprehension": 0.25},
                confidence=0.85,
                evidence={"example_count": example_count}
            ))
        
        # Check for CTAs
        cta_patterns = [
            r'click here',
            r'learn more',
            r'get started',
            r'try now',
            r'sign up',
            r'download',
            r'contact us'
        ]
        cta_count = sum(len(re.findall(pattern, content, re.IGNORECASE)) 
                       for pattern in cta_patterns)
        
        if cta_count == 0:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="eng_3",
                category="engagement",
                priority="high",
                description="No clear call-to-action found",
                implementation="Add a clear CTA at the end and optionally in the middle",
                expected_impact={"conversion": 0.4, "engagement": 0.2},
                confidence=0.9,
                evidence={"cta_count": cta_count}
            ))
        
        # Check emotional language
        emotion_score = await self._analyze_emotional_tone(content)
        if emotion_score < 0.3:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="eng_4",
                category="engagement",
                priority="low",
                description="Content lacks emotional appeal",
                implementation="Add power words and emotional triggers relevant to your audience",
                expected_impact={"engagement": 0.2, "shareability": 0.15},
                confidence=0.7,
                evidence={"emotion_score": emotion_score}
            ))
        
        return suggestions
    
    async def _analyze_semantic_coherence(
        self,
        content: str
    ) -> List[OptimizationSuggestion]:
        """Analyze semantic coherence of content"""
        suggestions = []
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        if len(paragraphs) > 1:
            # Generate embeddings for paragraphs
            embeddings = await self.model_manager.get_embeddings_batch(paragraphs)
            embeddings = embeddings.numpy()
            
            # Calculate coherence between consecutive paragraphs
            coherence_scores = []
            for i in range(len(embeddings) - 1):
                similarity = np.dot(embeddings[i], embeddings[i + 1])
                coherence_scores.append(similarity)
            
            # Find low coherence transitions
            low_coherence = [(i, score) for i, score in enumerate(coherence_scores) if score < 0.5]
            
            if low_coherence:
                suggestions.append(OptimizationSuggestion(
                    suggestion_id="coh_1",
                    category="content",
                    priority="medium",
                    description=f"Found {len(low_coherence)} weak transitions between paragraphs",
                    implementation="Add transitional phrases or sentences to improve flow",
                    expected_impact={"readability": 0.2, "engagement": 0.15},
                    confidence=0.8,
                    evidence={
                        "weak_transitions": low_coherence[:3],
                        "avg_coherence": np.mean(coherence_scores)
                    }
                ))
            
            # Check overall coherence
            avg_coherence = np.mean(coherence_scores)
            if avg_coherence < 0.6:
                suggestions.append(OptimizationSuggestion(
                    suggestion_id="coh_2",
                    category="content",
                    priority="high",
                    description="Overall content coherence is low",
                    implementation="Reorganize content to group related ideas together",
                    expected_impact={"readability": 0.3, "comprehension": 0.35},
                    confidence=0.85,
                    evidence={"avg_coherence": avg_coherence}
                ))
        
        return suggestions
    
    async def _analyze_competitive_position(
        self,
        content: str,
        competitive_content: List[str]
    ) -> List[OptimizationSuggestion]:
        """Analyze content against competition"""
        suggestions = []
        
        # Generate embeddings
        our_embedding = self.model_manager.get_embeddings(content)
        comp_embeddings = await self.model_manager.get_embeddings_batch(competitive_content)
        
        # Find unique angles
        similarities = [np.dot(our_embedding, comp_emb) for comp_emb in comp_embeddings]
        avg_similarity = np.mean(similarities)
        
        if avg_similarity > 0.8:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="comp_1",
                category="content",
                priority="high",
                description="Content too similar to competition",
                implementation="Add unique insights, data, or perspectives to differentiate",
                expected_impact={"uniqueness": 0.4, "authority": 0.3},
                confidence=0.85,
                evidence={
                    "avg_similarity": avg_similarity,
                    "max_similarity": max(similarities)
                }
            ))
        
        # Analyze length
        our_length = len(word_tokenize(content))
        comp_lengths = [len(word_tokenize(comp)) for comp in competitive_content]
        avg_comp_length = np.mean(comp_lengths)
        
        if our_length < avg_comp_length * 0.7:
            suggestions.append(OptimizationSuggestion(
                suggestion_id="comp_2",
                category="content",
                priority="medium",
                description="Content significantly shorter than competition",
                implementation=f"Expand content by {int(avg_comp_length - our_length)} words with additional sections",
                expected_impact={"seo": 0.25, "authority": 0.2},
                confidence=0.8,
                evidence={
                    "our_length": our_length,
                    "avg_comp_length": avg_comp_length
                }
            ))
        
        return suggestions
    
    async def _generate_lsi_keywords(
        self,
        content: str,
        target_keywords: List[str]
    ) -> List[str]:
        """Generate LSI keywords using embeddings"""
        # Get embeddings for target keywords
        keyword_embeddings = await self.model_manager.get_embeddings_batch(target_keywords)
        
        # Extract candidate terms from content
        words = word_tokenize(content.lower())
        word_freq = defaultdict(int)
        
        for word in words:
            if len(word) > 3 and word.isalpha():
                word_freq[word] += 1
        
        # Get top candidate terms
        candidates = [word for word, freq in word_freq.items() 
                     if freq > 1 and word not in target_keywords]
        
        if not candidates:
            return []
        
        # Get embeddings for candidates
        candidate_embeddings = await self.model_manager.get_embeddings_batch(candidates[:50])
        
        # Find semantically related terms
        lsi_keywords = []
        for i, (word, embedding) in enumerate(zip(candidates[:50], candidate_embeddings)):
            # Calculate similarity to target keywords
            similarities = [np.dot(embedding, kw_emb) for kw_emb in keyword_embeddings]
            max_similarity = max(similarities)
            
            if 0.5 < max_similarity < 0.8:  # Related but not identical
                lsi_keywords.append((word, max_similarity))
        
        # Sort by relevance
        lsi_keywords.sort(key=lambda x: x[1], reverse=True)
        
        return [word for word, _ in lsi_keywords[:10]]
    
    async def _analyze_emotional_tone(self, content: str) -> float:
        """Analyze emotional tone of content"""
        try:
            # Use sentiment analysis
            sentiment_scores = self.model_manager.analyze_sentiment(content)
            
            # Calculate emotional intensity
            positive = sentiment_scores.get('positive', 0) + sentiment_scores.get('very_positive', 0)
            negative = sentiment_scores.get('negative', 0) + sentiment_scores.get('very_negative', 0)
            
            emotional_intensity = abs(positive - negative) + (positive + negative) / 2
            return min(1.0, emotional_intensity)
        except:
            return 0.5  # Default neutral score
    
    def _prioritize_suggestions(
        self,
        suggestions: List[OptimizationSuggestion]
    ) -> List[OptimizationSuggestion]:
        """Prioritize suggestions based on impact and confidence"""
        # Calculate priority scores
        priority_weights = {"high": 3, "medium": 2, "low": 1}
        
        for suggestion in suggestions:
            # Calculate expected impact score
            impact_score = sum(suggestion.expected_impact.values()) / len(suggestion.expected_impact)
            
            # Calculate overall priority score
            priority_value = priority_weights.get(suggestion.priority, 1)
            suggestion.priority_score = (
                priority_value * 0.4 +
                impact_score * 0.4 +
                suggestion.confidence * 0.2
            )
        
        # Sort by priority score
        suggestions.sort(key=lambda x: x.priority_score, reverse=True)
        
        return suggestions
    
    def generate_optimization_report(
        self,
        suggestions: List[OptimizationSuggestion]
    ) -> Dict[str, Any]:
        """Generate optimization report"""
        report = {
            "summary": {
                "total_suggestions": len(suggestions),
                "high_priority": sum(1 for s in suggestions if s.priority == "high"),
                "categories": defaultdict(int),
                "expected_impact": defaultdict(float)
            },
            "suggestions": [],
            "implementation_plan": {
                "immediate": [],
                "short_term": [],
                "long_term": []
            }
        }
        
        # Process suggestions
        for suggestion in suggestions:
            report["summary"]["categories"][suggestion.category] += 1
            
            # Aggregate expected impact
            for metric, impact in suggestion.expected_impact.items():
                report["summary"]["expected_impact"][metric] += impact
            
            # Add to implementation plan
            if suggestion.priority == "high":
                report["implementation_plan"]["immediate"].append({
                    "id": suggestion.suggestion_id,
                    "description": suggestion.description,
                    "implementation": suggestion.implementation
                })
            elif suggestion.priority == "medium":
                report["implementation_plan"]["short_term"].append({
                    "id": suggestion.suggestion_id,
                    "description": suggestion.description,
                    "implementation": suggestion.implementation
                })
            else:
                report["implementation_plan"]["long_term"].append({
                    "id": suggestion.suggestion_id,
                    "description": suggestion.description,
                    "implementation": suggestion.implementation
                })
            
            # Add full suggestion
            report["suggestions"].append({
                "id": suggestion.suggestion_id,
                "category": suggestion.category,
                "priority": suggestion.priority,
                "description": suggestion.description,
                "implementation": suggestion.implementation,
                "expected_impact": suggestion.expected_impact,
                "confidence": suggestion.confidence
            })
        
        # Normalize expected impact
        total_suggestions = len(suggestions)
        if total_suggestions > 0:
            for metric in report["summary"]["expected_impact"]:
                report["summary"]["expected_impact"][metric] /= total_suggestions
        
        return report