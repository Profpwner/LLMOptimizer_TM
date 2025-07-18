"""
ML Package - Core optimization engine with semantic saturation
"""

from .model_manager import ModelManager, get_model_manager
from .embedding_pipeline import EmbeddingPipeline, EmbeddingConfig, TextChunk
from .similarity_engine import SimilarityEngine, SimilarityConfig, SearchResult
from .content_mesh import ContentMesh, ContentNode, ContentEdge, MeshConfig
from .gap_analysis import GapAnalysisEngine, GapAnalysisConfig, SemanticGap
from .visualization import VisualizationEngine, VisualizationConfig
from .optimization_engine import OptimizationEngine, OptimizationConfig, OptimizationSuggestion
from .semantic_saturation import (
    SemanticSaturationController,
    SemanticAnalysisRequest,
    SemanticAnalysisResult
)

__all__ = [
    # Model Management
    "ModelManager",
    "get_model_manager",
    
    # Embedding Pipeline
    "EmbeddingPipeline",
    "EmbeddingConfig",
    "TextChunk",
    
    # Similarity Engine
    "SimilarityEngine",
    "SimilarityConfig",
    "SearchResult",
    
    # Content Mesh
    "ContentMesh",
    "ContentNode",
    "ContentEdge",
    "MeshConfig",
    
    # Gap Analysis
    "GapAnalysisEngine",
    "GapAnalysisConfig",
    "SemanticGap",
    
    # Visualization
    "VisualizationEngine",
    "VisualizationConfig",
    
    # Optimization
    "OptimizationEngine",
    "OptimizationConfig",
    "OptimizationSuggestion",
    
    # Main Controller
    "SemanticSaturationController",
    "SemanticAnalysisRequest",
    "SemanticAnalysisResult"
]

# Version
__version__ = "1.0.0"