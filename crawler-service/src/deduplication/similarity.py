"""Content similarity calculation methods."""

import re
from typing import Dict, List, Tuple, Set, Any
from collections import Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import structlog

logger = structlog.get_logger(__name__)


class SimilarityCalculator:
    """Calculate content similarity using various methods."""
    
    def __init__(self):
        """Initialize similarity calculator."""
        self.tfidf_vectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            max_features=1000,
            stop_words='english'
        )
        self.stats = {
            'jaccard_calculations': 0,
            'cosine_calculations': 0,
            'levenshtein_calculations': 0,
            'semantic_calculations': 0
        }
    
    def jaccard_similarity(self, text1: str, text2: str, use_shingles: bool = True) -> float:
        """
        Calculate Jaccard similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            use_shingles: Use shingles instead of words
            
        Returns:
            Similarity score (0-1)
        """
        self.stats['jaccard_calculations'] += 1
        
        if use_shingles:
            set1 = self._extract_shingles(text1)
            set2 = self._extract_shingles(text2)
        else:
            set1 = set(self._tokenize(text1))
            set2 = set(self._tokenize(text2))
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def cosine_similarity_tfidf(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity using TF-IDF vectors.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        self.stats['cosine_calculations'] += 1
        
        try:
            # Fit and transform texts
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([text1, text2])
            
            # Calculate cosine similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            return float(similarity)
        except Exception as e:
            logger.warning(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def levenshtein_ratio(self, text1: str, text2: str, max_length: int = 1000) -> float:
        """
        Calculate normalized Levenshtein distance ratio.
        
        Args:
            text1: First text
            text2: Second text
            max_length: Maximum text length to consider
            
        Returns:
            Similarity ratio (0-1)
        """
        self.stats['levenshtein_calculations'] += 1
        
        # Truncate for performance
        text1 = text1[:max_length]
        text2 = text2[:max_length]
        
        distance = self._levenshtein_distance(text1, text2)
        max_len = max(len(text1), len(text2))
        
        return 1 - (distance / max_len) if max_len > 0 else 1.0
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def content_similarity_score(
        self,
        content1: str,
        content2: str,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive similarity score.
        
        Args:
            content1: First content
            content2: Second content
            weights: Weights for different similarity measures
            
        Returns:
            Similarity results with individual scores and combined score
        """
        if weights is None:
            weights = {
                'jaccard': 0.25,
                'cosine': 0.35,
                'structure': 0.20,
                'metadata': 0.20
            }
        
        # Normalize content
        norm_content1 = self._normalize_content(content1)
        norm_content2 = self._normalize_content(content2)
        
        # Calculate individual similarities
        scores = {
            'jaccard': self.jaccard_similarity(norm_content1, norm_content2),
            'cosine': self.cosine_similarity_tfidf(norm_content1, norm_content2),
            'structure': self._structural_similarity(content1, content2),
            'metadata': self._metadata_similarity(content1, content2)
        }
        
        # Calculate weighted score
        weighted_score = sum(scores[k] * weights.get(k, 0) for k in scores)
        
        # Determine similarity level
        if weighted_score >= 0.95:
            similarity_level = 'exact'
        elif weighted_score >= 0.80:
            similarity_level = 'near_duplicate'
        elif weighted_score >= 0.60:
            similarity_level = 'similar'
        elif weighted_score >= 0.40:
            similarity_level = 'somewhat_similar'
        else:
            similarity_level = 'different'
        
        return {
            'scores': scores,
            'weighted_score': round(weighted_score, 3),
            'similarity_level': similarity_level,
            'is_duplicate': weighted_score >= 0.80
        }
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for comparison."""
        # Convert to lowercase
        content = content.lower()
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Remove URLs
        content = re.sub(r'https?://[^\s]+', ' ', content)
        
        # Remove special characters
        content = re.sub(r'[^\w\s]', ' ', content)
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        return text.lower().split()
    
    def _extract_shingles(self, text: str, k: int = 3) -> Set[str]:
        """Extract k-shingles from text."""
        words = self._tokenize(text)
        shingles = set()
        
        for i in range(len(words) - k + 1):
            shingle = ' '.join(words[i:i + k])
            shingles.add(shingle)
        
        return shingles
    
    def _structural_similarity(self, content1: str, content2: str) -> float:
        """Calculate structural similarity based on content patterns."""
        # Extract structural features
        features1 = self._extract_structural_features(content1)
        features2 = self._extract_structural_features(content2)
        
        # Compare features
        similarity_scores = []
        
        # Length similarity
        len_ratio = min(features1['length'], features2['length']) / max(features1['length'], features2['length'])
        similarity_scores.append(len_ratio)
        
        # Paragraph count similarity
        para_ratio = min(features1['paragraphs'], features2['paragraphs']) / max(features1['paragraphs'], features2['paragraphs'], 1)
        similarity_scores.append(para_ratio)
        
        # Sentence count similarity
        sent_ratio = min(features1['sentences'], features2['sentences']) / max(features1['sentences'], features2['sentences'], 1)
        similarity_scores.append(sent_ratio)
        
        # Average word length similarity
        word_len_diff = abs(features1['avg_word_length'] - features2['avg_word_length'])
        word_len_sim = 1 - min(word_len_diff / 10, 1)
        similarity_scores.append(word_len_sim)
        
        return sum(similarity_scores) / len(similarity_scores)
    
    def _extract_structural_features(self, content: str) -> Dict[str, Any]:
        """Extract structural features from content."""
        words = content.split()
        sentences = re.findall(r'[.!?]+', content)
        paragraphs = re.findall(r'\n\n+', content)
        
        return {
            'length': len(content),
            'words': len(words),
            'sentences': len(sentences),
            'paragraphs': len(paragraphs) + 1,
            'avg_word_length': sum(len(w) for w in words) / len(words) if words else 0,
            'unique_words': len(set(words))
        }
    
    def _metadata_similarity(self, content1: str, content2: str) -> float:
        """Calculate metadata similarity (URLs, dates, numbers, etc.)."""
        # Extract metadata
        meta1 = self._extract_metadata(content1)
        meta2 = self._extract_metadata(content2)
        
        similarity_scores = []
        
        # URL similarity
        if meta1['urls'] or meta2['urls']:
            url_sim = len(meta1['urls'] & meta2['urls']) / len(meta1['urls'] | meta2['urls'])
            similarity_scores.append(url_sim)
        
        # Date similarity
        if meta1['dates'] or meta2['dates']:
            date_sim = len(meta1['dates'] & meta2['dates']) / len(meta1['dates'] | meta2['dates'])
            similarity_scores.append(date_sim)
        
        # Number similarity
        if meta1['numbers'] or meta2['numbers']:
            num_sim = len(meta1['numbers'] & meta2['numbers']) / len(meta1['numbers'] | meta2['numbers'])
            similarity_scores.append(num_sim)
        
        # Email similarity
        if meta1['emails'] or meta2['emails']:
            email_sim = len(meta1['emails'] & meta2['emails']) / len(meta1['emails'] | meta2['emails'])
            similarity_scores.append(email_sim)
        
        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.5
    
    def _extract_metadata(self, content: str) -> Dict[str, Set[str]]:
        """Extract metadata from content."""
        return {
            'urls': set(re.findall(r'https?://[^\s]+', content)),
            'dates': set(re.findall(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', content)),
            'numbers': set(re.findall(r'\b\d+\b', content)),
            'emails': set(re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content))
        }
    
    def find_similar_content(
        self,
        target_content: str,
        content_list: List[Tuple[str, str]],
        threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Find similar content from a list.
        
        Args:
            target_content: Target content to compare
            content_list: List of (id, content) tuples
            threshold: Similarity threshold
            
        Returns:
            List of similar content with scores
        """
        similar_content = []
        
        for content_id, content in content_list:
            similarity = self.content_similarity_score(target_content, content)
            
            if similarity['weighted_score'] >= threshold:
                similar_content.append({
                    'id': content_id,
                    'similarity': similarity['weighted_score'],
                    'level': similarity['similarity_level'],
                    'scores': similarity['scores']
                })
        
        # Sort by similarity score
        similar_content.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar_content
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get similarity calculation statistics."""
        return self.stats