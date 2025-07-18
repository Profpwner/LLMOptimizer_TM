"""
Gap Analysis Engine
Identifies semantic gaps and missing content areas using topic modeling and analysis
"""

import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation, NMF
from bertopic import BERTopic
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import torch

logger = logging.getLogger(__name__)


@dataclass
class SemanticGap:
    """Represents a semantic gap in content"""
    gap_id: str
    gap_type: str  # missing_topic, weak_coverage, competitor_advantage
    description: str
    severity: float  # 0-1 scale
    affected_topics: List[str]
    recommendations: List[str]
    evidence: Dict[str, Any]


@dataclass
class GapAnalysisConfig:
    """Configuration for gap analysis"""
    n_topics: int = 20
    topic_model: str = "lda"  # lda, nmf, bertopic
    min_topic_size: int = 10
    competitor_analysis: bool = True
    coverage_threshold: float = 0.7
    use_embeddings: bool = True


class GapAnalysisEngine:
    """Engine for analyzing semantic gaps in content"""
    
    def __init__(self, model_manager, similarity_engine):
        self.model_manager = model_manager
        self.similarity_engine = similarity_engine
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.topic_models = {}
        self.gaps = []
        
    async def analyze_gaps(
        self,
        content_items: List[Dict[str, Any]],
        reference_topics: Optional[List[str]] = None,
        competitor_content: Optional[List[Dict[str, Any]]] = None,
        config: Optional[GapAnalysisConfig] = None
    ) -> List[SemanticGap]:
        """Perform comprehensive gap analysis"""
        if config is None:
            config = GapAnalysisConfig()
        
        logger.info(f"Starting gap analysis on {len(content_items)} items")
        
        # Extract texts
        texts = [item.get("content", "") for item in content_items]
        
        # Perform topic modeling
        topics, topic_model = await self._perform_topic_modeling(texts, config)
        
        # Analyze topic coverage
        coverage_gaps = await self._analyze_topic_coverage(
            texts, topics, reference_topics, config
        )
        
        # Analyze semantic density
        density_gaps = await self._analyze_semantic_density(
            content_items, config
        )
        
        # Competitive analysis if enabled
        competitive_gaps = []
        if config.competitor_analysis and competitor_content:
            competitive_gaps = await self._analyze_competitive_gaps(
                content_items, competitor_content, config
            )
        
        # Combine all gaps
        self.gaps = coverage_gaps + density_gaps + competitive_gaps
        
        # Sort by severity
        self.gaps.sort(key=lambda x: x.severity, reverse=True)
        
        logger.info(f"Identified {len(self.gaps)} semantic gaps")
        return self.gaps
    
    async def _perform_topic_modeling(
        self,
        texts: List[str],
        config: GapAnalysisConfig
    ) -> Tuple[Dict[int, Dict[str, Any]], Any]:
        """Perform topic modeling on texts"""
        loop = asyncio.get_event_loop()
        
        def model_topics():
            if config.topic_model == "lda":
                # LDA topic modeling
                vectorizer = TfidfVectorizer(
                    max_features=1000,
                    min_df=2,
                    max_df=0.8,
                    stop_words='english'
                )
                doc_term_matrix = vectorizer.fit_transform(texts)
                
                lda = LatentDirichletAllocation(
                    n_components=config.n_topics,
                    random_state=42,
                    learning_method='batch'
                )
                lda.fit(doc_term_matrix)
                
                # Extract topics
                feature_names = vectorizer.get_feature_names_out()
                topics = {}
                
                for topic_idx, topic in enumerate(lda.components_):
                    top_indices = topic.argsort()[-10:][::-1]
                    top_words = [feature_names[i] for i in top_indices]
                    top_weights = topic[top_indices]
                    
                    topics[topic_idx] = {
                        "words": top_words,
                        "weights": top_weights.tolist(),
                        "coherence": self._calculate_topic_coherence(top_words, texts)
                    }
                
                return topics, lda
            
            elif config.topic_model == "nmf":
                # NMF topic modeling
                vectorizer = TfidfVectorizer(
                    max_features=1000,
                    min_df=2,
                    max_df=0.8,
                    stop_words='english'
                )
                doc_term_matrix = vectorizer.fit_transform(texts)
                
                nmf = NMF(
                    n_components=config.n_topics,
                    random_state=42,
                    init='nndsvd'
                )
                nmf.fit(doc_term_matrix)
                
                # Extract topics
                feature_names = vectorizer.get_feature_names_out()
                topics = {}
                
                for topic_idx, topic in enumerate(nmf.components_):
                    top_indices = topic.argsort()[-10:][::-1]
                    top_words = [feature_names[i] for i in top_indices]
                    top_weights = topic[top_indices]
                    
                    topics[topic_idx] = {
                        "words": top_words,
                        "weights": top_weights.tolist(),
                        "coherence": self._calculate_topic_coherence(top_words, texts)
                    }
                
                return topics, nmf
            
            else:  # bertopic
                # BERTopic modeling
                if config.use_embeddings and hasattr(self.model_manager, 'models'):
                    embedding_model = self.model_manager.models.get('embeddings')
                else:
                    embedding_model = None
                
                topic_model = BERTopic(
                    embedding_model=embedding_model,
                    nr_topics=config.n_topics,
                    min_topic_size=config.min_topic_size
                )
                
                topics_list, probs = topic_model.fit_transform(texts)
                
                # Extract topic information
                topics = {}
                topic_info = topic_model.get_topic_info()
                
                for idx, row in topic_info.iterrows():
                    if row['Topic'] != -1:  # Skip outlier topic
                        topic_words = topic_model.get_topic(row['Topic'])
                        topics[row['Topic']] = {
                            "words": [word for word, _ in topic_words[:10]],
                            "weights": [float(weight) for _, weight in topic_words[:10]],
                            "size": row['Count'],
                            "name": row['Name']
                        }
                
                return topics, topic_model
        
        topics, model = await loop.run_in_executor(self.executor, model_topics)
        self.topic_models[config.topic_model] = model
        
        return topics, model
    
    def _calculate_topic_coherence(
        self,
        words: List[str],
        texts: List[str]
    ) -> float:
        """Calculate coherence score for a topic"""
        # Simple coherence based on co-occurrence
        word_pairs = []
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                word_pairs.append((words[i], words[j]))
        
        if not word_pairs:
            return 0.0
        
        coherence_scores = []
        for w1, w2 in word_pairs:
            co_occur = sum(1 for text in texts if w1 in text and w2 in text)
            w1_occur = sum(1 for text in texts if w1 in text)
            w2_occur = sum(1 for text in texts if w2 in text)
            
            if w1_occur > 0 and w2_occur > 0:
                pmi = np.log((co_occur * len(texts)) / (w1_occur * w2_occur) + 1e-10)
                coherence_scores.append(max(0, pmi))
        
        return np.mean(coherence_scores) if coherence_scores else 0.0
    
    async def _analyze_topic_coverage(
        self,
        texts: List[str],
        discovered_topics: Dict[int, Dict[str, Any]],
        reference_topics: Optional[List[str]],
        config: GapAnalysisConfig
    ) -> List[SemanticGap]:
        """Analyze coverage of topics"""
        gaps = []
        
        # Check coverage of reference topics if provided
        if reference_topics:
            # Generate embeddings for reference topics
            ref_embeddings = await self.model_manager.get_embeddings_batch(
                reference_topics
            )
            
            # Generate embeddings for discovered topic words
            discovered_embeddings = []
            topic_labels = []
            
            for topic_id, topic_info in discovered_topics.items():
                topic_text = " ".join(topic_info["words"][:5])
                topic_labels.append(topic_id)
                discovered_embeddings.append(
                    self.model_manager.get_embeddings(topic_text)
                )
            
            discovered_embeddings = torch.stack(discovered_embeddings).numpy()
            
            # Calculate coverage matrix
            coverage_matrix = np.dot(ref_embeddings, discovered_embeddings.T)
            
            # Find uncovered reference topics
            for i, ref_topic in enumerate(reference_topics):
                max_coverage = np.max(coverage_matrix[i])
                
                if max_coverage < config.coverage_threshold:
                    gap = SemanticGap(
                        gap_id=f"coverage_{i}",
                        gap_type="missing_topic",
                        description=f"Poor coverage of reference topic: {ref_topic}",
                        severity=1.0 - max_coverage,
                        affected_topics=[ref_topic],
                        recommendations=[
                            f"Create content covering '{ref_topic}'",
                            f"Expand existing content to include '{ref_topic}' concepts",
                            f"Consider adding dedicated section for '{ref_topic}'"
                        ],
                        evidence={
                            "reference_topic": ref_topic,
                            "best_coverage_score": float(max_coverage),
                            "coverage_threshold": config.coverage_threshold
                        }
                    )
                    gaps.append(gap)
        
        # Check for weak topics (low coherence or small size)
        for topic_id, topic_info in discovered_topics.items():
            coherence = topic_info.get("coherence", 0)
            size = topic_info.get("size", 0)
            
            if coherence < 0.3 or size < config.min_topic_size:
                gap = SemanticGap(
                    gap_id=f"weak_topic_{topic_id}",
                    gap_type="weak_coverage",
                    description=f"Weak topic with low coherence or size",
                    severity=0.7,
                    affected_topics=topic_info["words"][:5],
                    recommendations=[
                        "Strengthen content in this topic area",
                        "Add more comprehensive coverage",
                        "Improve content structure and coherence"
                    ],
                    evidence={
                        "topic_id": topic_id,
                        "coherence": coherence,
                        "size": size,
                        "top_words": topic_info["words"][:5]
                    }
                )
                gaps.append(gap)
        
        return gaps
    
    async def _analyze_semantic_density(
        self,
        content_items: List[Dict[str, Any]],
        config: GapAnalysisConfig
    ) -> List[SemanticGap]:
        """Analyze semantic density and identify sparse areas"""
        gaps = []
        
        if len(content_items) < 2:
            return gaps
        
        # Generate embeddings for all content
        texts = [item.get("content", "") for item in content_items]
        embeddings = await self.model_manager.get_embeddings_batch(texts)
        
        # Calculate pairwise similarities
        similarities = self.similarity_engine.compute_pairwise_similarities(
            embeddings.numpy()
        )
        
        # Find content islands (poorly connected content)
        for i, item in enumerate(content_items):
            # Get similarities to other content
            item_similarities = similarities[i]
            item_similarities[i] = 0  # Exclude self-similarity
            
            # Check if content is isolated
            max_similarity = np.max(item_similarities)
            avg_similarity = np.mean(item_similarities)
            
            if max_similarity < 0.5:  # No strong connections
                gap = SemanticGap(
                    gap_id=f"island_{i}",
                    gap_type="content_island",
                    description=f"Isolated content with weak connections",
                    severity=0.8,
                    affected_topics=[item.get("title", f"Content {i}")],
                    recommendations=[
                        "Create bridging content to connect this topic",
                        "Expand content to include related concepts",
                        "Add cross-references to related content"
                    ],
                    evidence={
                        "content_id": item.get("id", i),
                        "max_similarity": float(max_similarity),
                        "avg_similarity": float(avg_similarity)
                    }
                )
                gaps.append(gap)
        
        # Identify sparse regions using clustering
        labels, cluster_info = await self.similarity_engine.cluster_embeddings(
            embeddings.numpy(),
            config={"clustering_algorithm": "dbscan"}
        )
        
        # Check for small or sparse clusters
        cluster_sizes = defaultdict(int)
        for label in labels:
            if label != -1:  # Ignore noise
                cluster_sizes[label] += 1
        
        for cluster_id, size in cluster_sizes.items():
            if size < 3:  # Small cluster
                cluster_items = [
                    content_items[i] for i, label in enumerate(labels) 
                    if label == cluster_id
                ]
                
                gap = SemanticGap(
                    gap_id=f"sparse_cluster_{cluster_id}",
                    gap_type="sparse_region",
                    description=f"Sparse semantic region with few content items",
                    severity=0.6,
                    affected_topics=[
                        item.get("title", f"Content {i}") 
                        for i, item in enumerate(cluster_items)
                    ],
                    recommendations=[
                        "Add more content in this semantic area",
                        "Diversify content within this topic",
                        "Consider merging with related topics"
                    ],
                    evidence={
                        "cluster_id": int(cluster_id),
                        "cluster_size": size,
                        "min_recommended_size": 3
                    }
                )
                gaps.append(gap)
        
        return gaps
    
    async def _analyze_competitive_gaps(
        self,
        content_items: List[Dict[str, Any]],
        competitor_content: List[Dict[str, Any]],
        config: GapAnalysisConfig
    ) -> List[SemanticGap]:
        """Analyze gaps compared to competitor content"""
        gaps = []
        
        # Generate embeddings
        our_texts = [item.get("content", "") for item in content_items]
        comp_texts = [item.get("content", "") for item in competitor_content]
        
        our_embeddings = await self.model_manager.get_embeddings_batch(our_texts)
        comp_embeddings = await self.model_manager.get_embeddings_batch(comp_texts)
        
        # Find competitor topics not well covered
        for i, comp_item in enumerate(competitor_content):
            comp_embedding = comp_embeddings[i].numpy()
            
            # Find best match in our content
            similarities = [
                np.dot(comp_embedding, our_emb.numpy())
                for our_emb in our_embeddings
            ]
            
            max_similarity = max(similarities) if similarities else 0
            
            if max_similarity < config.coverage_threshold:
                gap = SemanticGap(
                    gap_id=f"competitive_{i}",
                    gap_type="competitor_advantage",
                    description=f"Competitor covers topic not well addressed",
                    severity=1.0 - max_similarity,
                    affected_topics=[comp_item.get("title", f"Competitor topic {i}")],
                    recommendations=[
                        f"Create content similar to: {comp_item.get('title', 'competitor topic')}",
                        "Analyze competitor's approach and improve upon it",
                        "Consider unique angle on this topic"
                    ],
                    evidence={
                        "competitor_topic": comp_item.get("title", ""),
                        "best_match_similarity": float(max_similarity),
                        "competitor_metrics": comp_item.get("metrics", {})
                    }
                )
                gaps.append(gap)
        
        return gaps
    
    def prioritize_gaps(
        self,
        gaps: Optional[List[SemanticGap]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> List[SemanticGap]:
        """Prioritize gaps based on various factors"""
        if gaps is None:
            gaps = self.gaps
        
        if weights is None:
            weights = {
                "missing_topic": 1.0,
                "weak_coverage": 0.8,
                "content_island": 0.7,
                "sparse_region": 0.6,
                "competitor_advantage": 0.9
            }
        
        # Calculate priority scores
        for gap in gaps:
            base_score = gap.severity
            type_weight = weights.get(gap.gap_type, 0.5)
            gap.priority_score = base_score * type_weight
        
        # Sort by priority
        gaps.sort(key=lambda x: x.priority_score, reverse=True)
        
        return gaps
    
    def generate_gap_report(self) -> Dict[str, Any]:
        """Generate comprehensive gap analysis report"""
        report = {
            "summary": {
                "total_gaps": len(self.gaps),
                "gaps_by_type": defaultdict(int),
                "average_severity": 0,
                "critical_gaps": 0
            },
            "gaps": [],
            "recommendations": {
                "immediate_actions": [],
                "short_term": [],
                "long_term": []
            }
        }
        
        # Analyze gaps
        severities = []
        for gap in self.gaps:
            report["summary"]["gaps_by_type"][gap.gap_type] += 1
            severities.append(gap.severity)
            
            if gap.severity > 0.8:
                report["summary"]["critical_gaps"] += 1
            
            # Add gap details
            gap_detail = {
                "id": gap.gap_id,
                "type": gap.gap_type,
                "description": gap.description,
                "severity": gap.severity,
                "affected_topics": gap.affected_topics,
                "recommendations": gap.recommendations
            }
            report["gaps"].append(gap_detail)
            
            # Categorize recommendations
            if gap.severity > 0.8:
                report["recommendations"]["immediate_actions"].extend(
                    gap.recommendations[:1]
                )
            elif gap.severity > 0.6:
                report["recommendations"]["short_term"].extend(
                    gap.recommendations[:1]
                )
            else:
                report["recommendations"]["long_term"].extend(
                    gap.recommendations[:1]
                )
        
        # Calculate summary statistics
        if severities:
            report["summary"]["average_severity"] = float(np.mean(severities))
        
        # Remove duplicates from recommendations
        for category in report["recommendations"]:
            report["recommendations"][category] = list(
                dict.fromkeys(report["recommendations"][category])
            )
        
        return report