"""
Semantic Saturation Controller
Main orchestrator for the semantic analysis and optimization pipeline
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime
import json

from .model_manager import get_model_manager
from .embedding_pipeline import EmbeddingPipeline, EmbeddingConfig
from .similarity_engine import SimilarityEngine, SimilarityConfig
from .content_mesh import ContentMesh, ContentNode, MeshConfig
from .gap_analysis import GapAnalysisEngine, GapAnalysisConfig
from .visualization import VisualizationEngine, VisualizationConfig
from .optimization_engine import OptimizationEngine, OptimizationConfig

logger = logging.getLogger(__name__)


@dataclass
class SemanticAnalysisRequest:
    """Request for semantic analysis"""
    content_items: List[Dict[str, Any]]
    target_keywords: List[str]
    reference_topics: Optional[List[str]] = None
    competitor_content: Optional[List[Dict[str, Any]]] = None
    optimization_goals: List[str] = None
    analysis_config: Optional[Dict[str, Any]] = None


@dataclass
class SemanticAnalysisResult:
    """Result of semantic analysis"""
    request_id: str
    timestamp: datetime
    content_mesh: Dict[str, Any]
    semantic_gaps: List[Dict[str, Any]]
    optimization_suggestions: List[Dict[str, Any]]
    visualizations: Dict[str, Any]
    metrics: Dict[str, float]
    processing_time: float


class SemanticSaturationController:
    """Main controller for semantic saturation analysis"""
    
    def __init__(self, redis_client=None, mongodb_client=None):
        self.redis_client = redis_client
        self.mongodb_client = mongodb_client
        self.model_manager = None
        self.components_initialized = False
        
        # Component instances
        self.embedding_pipeline = None
        self.similarity_engine = None
        self.content_mesh = None
        self.gap_analysis_engine = None
        self.visualization_engine = None
        self.optimization_engine = None
    
    async def initialize(self):
        """Initialize all components"""
        if self.components_initialized:
            return
        
        logger.info("Initializing Semantic Saturation Controller")
        
        # Initialize model manager
        self.model_manager = await get_model_manager()
        
        # Initialize components
        self.embedding_pipeline = EmbeddingPipeline(
            self.model_manager,
            self.redis_client
        )
        
        self.similarity_engine = SimilarityEngine()
        
        self.gap_analysis_engine = GapAnalysisEngine(
            self.model_manager,
            self.similarity_engine
        )
        
        self.visualization_engine = VisualizationEngine()
        
        self.optimization_engine = OptimizationEngine(
            self.model_manager,
            self.similarity_engine,
            self.gap_analysis_engine
        )
        
        self.components_initialized = True
        logger.info("Semantic Saturation Controller initialized successfully")
    
    async def analyze_content(
        self,
        request: SemanticAnalysisRequest
    ) -> SemanticAnalysisResult:
        """Perform comprehensive semantic analysis"""
        start_time = datetime.utcnow()
        request_id = f"sem_{start_time.timestamp()}"
        
        # Ensure components are initialized
        await self.initialize()
        
        logger.info(f"Starting semantic analysis for request {request_id}")
        
        try:
            # Step 1: Generate embeddings for all content
            embeddings = await self._generate_content_embeddings(request.content_items)
            
            # Step 2: Build content mesh
            content_mesh_data = await self._build_content_mesh(
                request.content_items,
                embeddings
            )
            
            # Step 3: Analyze semantic gaps
            semantic_gaps = await self._analyze_gaps(
                request.content_items,
                request.reference_topics,
                request.competitor_content
            )
            
            # Step 4: Generate optimization suggestions
            optimization_suggestions = await self._generate_optimizations(
                request.content_items,
                request.target_keywords,
                request.competitor_content
            )
            
            # Step 5: Create visualizations
            visualizations = await self._create_visualizations(
                content_mesh_data,
                semantic_gaps,
                embeddings
            )
            
            # Step 6: Calculate metrics
            metrics = self._calculate_metrics(
                content_mesh_data,
                semantic_gaps,
                optimization_suggestions
            )
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create result
            result = SemanticAnalysisResult(
                request_id=request_id,
                timestamp=start_time,
                content_mesh=content_mesh_data,
                semantic_gaps=semantic_gaps,
                optimization_suggestions=optimization_suggestions,
                visualizations=visualizations,
                metrics=metrics,
                processing_time=processing_time
            )
            
            # Cache result if Redis available
            if self.redis_client:
                await self._cache_result(result)
            
            # Store in MongoDB if available
            if self.mongodb_client:
                await self._store_result(result)
            
            logger.info(f"Semantic analysis completed for request {request_id} in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in semantic analysis: {e}")
            raise
    
    async def _generate_content_embeddings(
        self,
        content_items: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Generate embeddings for all content items"""
        logger.info(f"Generating embeddings for {len(content_items)} items")
        
        # Extract content texts
        texts = [item.get("content", "") for item in content_items]
        
        # Configure embedding generation
        config = EmbeddingConfig(
            model_type="default",
            chunk_size=512,
            chunk_overlap=50,
            normalize=True,
            cache_embeddings=True
        )
        
        # Generate embeddings
        embeddings = await self.embedding_pipeline.generate_embeddings(texts, config)
        
        return np.array(embeddings)
    
    async def _build_content_mesh(
        self,
        content_items: List[Dict[str, Any]],
        embeddings: np.ndarray
    ) -> Dict[str, Any]:
        """Build content mesh from items and embeddings"""
        logger.info("Building content mesh")
        
        # Create content nodes
        nodes = []
        for i, (item, embedding) in enumerate(zip(content_items, embeddings)):
            node = ContentNode(
                id=item.get("id", f"content_{i}"),
                title=item.get("title", f"Content {i}"),
                content=item.get("content", ""),
                embedding=embedding,
                metadata=item.get("metadata", {}),
                node_type=item.get("type", "content")
            )
            nodes.append(node)
        
        # Configure mesh building
        mesh_config = MeshConfig(
            similarity_threshold=0.7,
            max_edges_per_node=10,
            min_community_size=2,
            use_pagerank=True,
            use_community_detection=True
        )
        
        # Build mesh
        self.content_mesh = ContentMesh(self.similarity_engine)
        await self.content_mesh.build_mesh(nodes, mesh_config)
        
        # Get mesh statistics
        stats = self.content_mesh.get_mesh_statistics()
        
        # Find content gaps in mesh
        gaps = self.content_mesh.find_content_gaps()
        
        # Export mesh data
        mesh_data = {
            "nodes": len(nodes),
            "edges": stats["num_edges"],
            "communities": stats["num_communities"],
            "density": stats["density"],
            "gaps": gaps,
            "graph_data": json.loads(self.content_mesh.export_mesh("json"))
        }
        
        return mesh_data
    
    async def _analyze_gaps(
        self,
        content_items: List[Dict[str, Any]],
        reference_topics: Optional[List[str]],
        competitor_content: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Analyze semantic gaps"""
        logger.info("Analyzing semantic gaps")
        
        # Configure gap analysis
        config = GapAnalysisConfig(
            n_topics=20,
            topic_model="lda",
            competitor_analysis=competitor_content is not None,
            coverage_threshold=0.7,
            use_embeddings=True
        )
        
        # Perform gap analysis
        gaps = await self.gap_analysis_engine.analyze_gaps(
            content_items,
            reference_topics,
            competitor_content,
            config
        )
        
        # Prioritize gaps
        prioritized_gaps = self.gap_analysis_engine.prioritize_gaps(gaps)
        
        # Generate gap report
        gap_report = self.gap_analysis_engine.generate_gap_report()
        
        # Convert to serializable format
        gap_data = []
        for gap in prioritized_gaps:
            gap_data.append({
                "id": gap.gap_id,
                "type": gap.gap_type,
                "description": gap.description,
                "severity": gap.severity,
                "affected_topics": gap.affected_topics,
                "recommendations": gap.recommendations,
                "priority_score": getattr(gap, 'priority_score', gap.severity)
            })
        
        return gap_data
    
    async def _generate_optimizations(
        self,
        content_items: List[Dict[str, Any]],
        target_keywords: List[str],
        competitor_content: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Generate optimization suggestions"""
        logger.info("Generating optimization suggestions")
        
        optimization_data = []
        
        # Configure optimization
        config = OptimizationConfig(
            target_reading_level=8,
            keyword_density=0.02,
            engagement_factors=["questions", "examples", "visuals", "cta"]
        )
        
        # Generate optimizations for each content item
        for item in content_items[:5]:  # Limit to first 5 for performance
            content = item.get("content", "")
            metadata = item.get("metadata", {})
            
            # Extract competitor content texts if available
            comp_texts = None
            if competitor_content:
                comp_texts = [c.get("content", "") for c in competitor_content[:3]]
            
            # Generate suggestions
            suggestions = await self.optimization_engine.generate_optimizations(
                content,
                metadata,
                target_keywords,
                comp_texts,
                config
            )
            
            # Convert to serializable format
            for suggestion in suggestions[:10]:  # Limit suggestions per item
                optimization_data.append({
                    "content_id": item.get("id", "unknown"),
                    "suggestion_id": suggestion.suggestion_id,
                    "category": suggestion.category,
                    "priority": suggestion.priority,
                    "description": suggestion.description,
                    "implementation": suggestion.implementation,
                    "expected_impact": suggestion.expected_impact,
                    "confidence": suggestion.confidence
                })
        
        return optimization_data
    
    async def _create_visualizations(
        self,
        content_mesh_data: Dict[str, Any],
        semantic_gaps: List[Dict[str, Any]],
        embeddings: np.ndarray
    ) -> Dict[str, Any]:
        """Create visualizations"""
        logger.info("Creating visualizations")
        
        visualizations = {}
        
        # Configure visualization
        config = VisualizationConfig(
            layout_algorithm="force",
            node_size_metric="pagerank",
            color_by="community",
            dimensions=3,
            show_labels=True
        )
        
        # Create 3D network visualization
        if self.content_mesh:
            network_viz = self.visualization_engine.generate_3d_network(
                self.content_mesh,
                config
            )
            
            visualizations["network_3d"] = {
                "plotly_html": network_viz["plotly_figure"].to_html(div_id="network_3d"),
                "threejs_data": network_viz["threejs_data"]
            }
        
        # Create gap visualization
        if semantic_gaps:
            # Convert gap data back to objects for visualization
            gap_objects = [type('Gap', (), gap) for gap in semantic_gaps]
            gap_viz = self.visualization_engine.generate_gap_visualization(gap_objects)
            
            visualizations["gap_analysis"] = gap_viz.to_html(div_id="gap_analysis")
        
        # Create embedding visualization
        if len(embeddings) > 0:
            embedding_viz = self.visualization_engine.generate_embedding_visualization(
                embeddings[:100],  # Limit for performance
                method="pca"
            )
            
            visualizations["embeddings"] = embedding_viz.to_html(div_id="embeddings")
        
        return visualizations
    
    def _calculate_metrics(
        self,
        content_mesh_data: Dict[str, Any],
        semantic_gaps: List[Dict[str, Any]],
        optimization_suggestions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate analysis metrics"""
        metrics = {}
        
        # Content mesh metrics
        metrics["content_density"] = content_mesh_data.get("density", 0)
        metrics["content_communities"] = content_mesh_data.get("communities", 0)
        metrics["content_connectivity"] = 1 - (len(content_mesh_data.get("gaps", [])) / 
                                             max(content_mesh_data.get("nodes", 1), 1))
        
        # Gap metrics
        if semantic_gaps:
            severities = [gap["severity"] for gap in semantic_gaps]
            metrics["avg_gap_severity"] = np.mean(severities)
            metrics["critical_gaps"] = sum(1 for gap in semantic_gaps if gap["severity"] > 0.8)
            metrics["total_gaps"] = len(semantic_gaps)
        else:
            metrics["avg_gap_severity"] = 0
            metrics["critical_gaps"] = 0
            metrics["total_gaps"] = 0
        
        # Optimization metrics
        if optimization_suggestions:
            high_priority = sum(1 for opt in optimization_suggestions if opt["priority"] == "high")
            metrics["high_priority_optimizations"] = high_priority
            metrics["total_optimizations"] = len(optimization_suggestions)
            
            # Calculate potential impact
            impacts = []
            for opt in optimization_suggestions:
                if opt["expected_impact"]:
                    impacts.extend(opt["expected_impact"].values())
            metrics["avg_expected_impact"] = np.mean(impacts) if impacts else 0
        else:
            metrics["high_priority_optimizations"] = 0
            metrics["total_optimizations"] = 0
            metrics["avg_expected_impact"] = 0
        
        # Overall health score
        metrics["semantic_health_score"] = self._calculate_health_score(metrics)
        
        return metrics
    
    def _calculate_health_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall semantic health score"""
        # Weighted scoring
        score = 0
        
        # Content connectivity (30%)
        score += metrics.get("content_connectivity", 0) * 0.3
        
        # Gap severity (30%) - inverse
        gap_score = 1 - metrics.get("avg_gap_severity", 0)
        score += gap_score * 0.3
        
        # Content density (20%)
        density_score = min(1, metrics.get("content_density", 0) * 2)
        score += density_score * 0.2
        
        # Optimization potential (20%) - inverse
        opt_ratio = metrics.get("high_priority_optimizations", 0) / max(metrics.get("total_optimizations", 1), 1)
        opt_score = 1 - opt_ratio
        score += opt_score * 0.2
        
        return round(score, 3)
    
    async def _cache_result(self, result: SemanticAnalysisResult):
        """Cache analysis result in Redis"""
        try:
            # Convert to JSON-serializable format
            cache_data = {
                "request_id": result.request_id,
                "timestamp": result.timestamp.isoformat(),
                "metrics": result.metrics,
                "processing_time": result.processing_time
            }
            
            await self.redis_client.setex(
                f"semantic_analysis:{result.request_id}",
                3600 * 24,  # 24 hours
                json.dumps(cache_data)
            )
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
    
    async def _store_result(self, result: SemanticAnalysisResult):
        """Store analysis result in MongoDB"""
        try:
            # Convert to document format
            document = {
                "_id": result.request_id,
                "timestamp": result.timestamp,
                "content_mesh": result.content_mesh,
                "semantic_gaps": result.semantic_gaps,
                "optimization_suggestions": result.optimization_suggestions,
                "metrics": result.metrics,
                "processing_time": result.processing_time
            }
            
            await self.mongodb_client.semantic_analysis.insert_one(document)
        except Exception as e:
            logger.warning(f"Failed to store result: {e}")
    
    async def get_analysis_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve analysis result by ID"""
        # Try cache first
        if self.redis_client:
            try:
                cached = await self.redis_client.get(f"semantic_analysis:{request_id}")
                if cached:
                    return json.loads(cached)
            except:
                pass
        
        # Try MongoDB
        if self.mongodb_client:
            try:
                result = await self.mongodb_client.semantic_analysis.find_one({"_id": request_id})
                if result:
                    result["request_id"] = result.pop("_id")
                    return result
            except:
                pass
        
        return None
    
    def cleanup(self):
        """Clean up resources"""
        if self.model_manager:
            self.model_manager.cleanup()
        if self.similarity_engine:
            self.similarity_engine.cleanup()
        
        logger.info("Semantic Saturation Controller cleaned up")