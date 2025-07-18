"""
Tests for Semantic Saturation Engine
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from src.ml import (
    SemanticSaturationController,
    SemanticAnalysisRequest,
    ModelManager,
    EmbeddingPipeline,
    SimilarityEngine,
    ContentMesh,
    GapAnalysisEngine,
    VisualizationEngine,
    OptimizationEngine
)


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB client"""
    mongodb = AsyncMock()
    mongodb.semantic_analysis = AsyncMock()
    mongodb.semantic_analysis.insert_one = AsyncMock()
    return mongodb


@pytest.fixture
def sample_content_items():
    """Sample content items for testing"""
    return [
        {
            "id": "1",
            "title": "Introduction to Machine Learning",
            "content": "Machine learning is a subset of artificial intelligence that focuses on the development of algorithms and statistical models that enable computer systems to improve their performance on a specific task through experience.",
            "metadata": {"category": "ML basics"}
        },
        {
            "id": "2",
            "title": "Deep Learning Fundamentals",
            "content": "Deep learning is a subfield of machine learning that is inspired by the structure and function of the brain called artificial neural networks. It uses multiple layers to progressively extract higher-level features from raw input.",
            "metadata": {"category": "Deep learning"}
        },
        {
            "id": "3",
            "title": "Natural Language Processing",
            "content": "Natural Language Processing (NLP) is a branch of artificial intelligence that helps computers understand, interpret and manipulate human language. NLP draws from many disciplines including computer science and computational linguistics.",
            "metadata": {"category": "NLP"}
        }
    ]


@pytest.fixture
def sample_analysis_request(sample_content_items):
    """Sample semantic analysis request"""
    return SemanticAnalysisRequest(
        content_items=sample_content_items,
        target_keywords=["machine learning", "AI", "deep learning"],
        reference_topics=["neural networks", "supervised learning", "unsupervised learning"],
        optimization_goals=["seo", "readability", "engagement"]
    )


class TestSemanticSaturationController:
    """Test the main semantic saturation controller"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_redis, mock_mongodb):
        """Test controller initialization"""
        controller = SemanticSaturationController(
            redis_client=mock_redis,
            mongodb_client=mock_mongodb
        )
        
        assert controller.redis_client == mock_redis
        assert controller.mongodb_client == mock_mongodb
        assert not controller.components_initialized
        
        # Mock model manager
        with patch('src.ml.semantic_saturation.get_model_manager') as mock_get_model:
            mock_model_manager = Mock(spec=ModelManager)
            mock_get_model.return_value = mock_model_manager
            
            await controller.initialize()
            
            assert controller.components_initialized
            assert controller.model_manager is not None
            assert controller.embedding_pipeline is not None
            assert controller.similarity_engine is not None
    
    @pytest.mark.asyncio
    async def test_analyze_content(self, mock_redis, mock_mongodb, sample_analysis_request):
        """Test content analysis"""
        controller = SemanticSaturationController(
            redis_client=mock_redis,
            mongodb_client=mock_mongodb
        )
        
        # Mock all components
        with patch.object(controller, 'initialize', new_callable=AsyncMock):
            controller.components_initialized = True
            
            # Mock component methods
            with patch.object(controller, '_generate_content_embeddings', new_callable=AsyncMock) as mock_embeddings:
                mock_embeddings.return_value = np.random.rand(3, 384)  # 3 items, 384 dimensions
                
                with patch.object(controller, '_build_content_mesh', new_callable=AsyncMock) as mock_mesh:
                    mock_mesh.return_value = {
                        "nodes": 3,
                        "edges": 2,
                        "communities": 1,
                        "density": 0.667,
                        "gaps": []
                    }
                    
                    with patch.object(controller, '_analyze_gaps', new_callable=AsyncMock) as mock_gaps:
                        mock_gaps.return_value = [
                            {
                                "id": "gap_1",
                                "type": "missing_topic",
                                "description": "Poor coverage of supervised learning",
                                "severity": 0.7,
                                "affected_topics": ["supervised learning"],
                                "recommendations": ["Add content about supervised learning"]
                            }
                        ]
                        
                        with patch.object(controller, '_generate_optimizations', new_callable=AsyncMock) as mock_opts:
                            mock_opts.return_value = [
                                {
                                    "content_id": "1",
                                    "category": "readability",
                                    "priority": "high",
                                    "description": "Simplify complex sentences",
                                    "expected_impact": {"readability": 0.3}
                                }
                            ]
                            
                            with patch.object(controller, '_create_visualizations', new_callable=AsyncMock) as mock_viz:
                                mock_viz.return_value = {
                                    "network_3d": {"plotly_html": "<div>...</div>"},
                                    "gap_analysis": "<div>...</div>"
                                }
                                
                                # Perform analysis
                                result = await controller.analyze_content(sample_analysis_request)
                                
                                # Verify result
                                assert result.request_id.startswith("sem_")
                                assert result.content_mesh["nodes"] == 3
                                assert len(result.semantic_gaps) == 1
                                assert len(result.optimization_suggestions) == 1
                                assert "network_3d" in result.visualizations
                                assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_calculate_health_score(self, mock_redis, mock_mongodb):
        """Test semantic health score calculation"""
        controller = SemanticSaturationController()
        
        metrics = {
            "content_connectivity": 0.8,
            "avg_gap_severity": 0.3,
            "content_density": 0.4,
            "high_priority_optimizations": 2,
            "total_optimizations": 10
        }
        
        score = controller._calculate_health_score(metrics)
        
        # Score should be between 0 and 1
        assert 0 <= score <= 1
        
        # Test edge cases
        perfect_metrics = {
            "content_connectivity": 1.0,
            "avg_gap_severity": 0.0,
            "content_density": 0.5,
            "high_priority_optimizations": 0,
            "total_optimizations": 10
        }
        perfect_score = controller._calculate_health_score(perfect_metrics)
        assert perfect_score > 0.9


class TestEmbeddingPipeline:
    """Test embedding pipeline functionality"""
    
    @pytest.mark.asyncio
    async def test_generate_embeddings(self):
        """Test embedding generation"""
        # Mock model manager
        mock_model_manager = Mock(spec=ModelManager)
        mock_model_manager.get_embeddings_batch = AsyncMock()
        mock_model_manager.get_embeddings_batch.return_value = np.random.rand(3, 384)
        
        pipeline = EmbeddingPipeline(mock_model_manager)
        
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = await pipeline.generate_embeddings(texts)
        
        assert len(embeddings) == 3
        assert all(isinstance(emb, np.ndarray) for emb in embeddings)
    
    def test_chunk_text(self):
        """Test text chunking"""
        mock_model_manager = Mock()
        pipeline = EmbeddingPipeline(mock_model_manager)
        
        long_text = " ".join(["This is a sentence."] * 100)
        chunks = pipeline.chunk_text(long_text, config=Mock(chunk_size=512, chunk_overlap=50))
        
        assert len(chunks) > 1
        assert all(hasattr(chunk, 'text') for chunk in chunks)
        assert all(hasattr(chunk, 'start_index') for chunk in chunks)


class TestSimilarityEngine:
    """Test similarity computation engine"""
    
    @pytest.mark.asyncio
    async def test_build_index(self):
        """Test similarity index building"""
        engine = SimilarityEngine()
        
        # Create sample embeddings
        embeddings = np.random.rand(10, 128).astype(np.float32)
        
        await engine.build_index(embeddings, "test_index")
        
        assert "test_index" in engine.indices
        assert engine.indices["test_index"]["size"] == 10
    
    @pytest.mark.asyncio
    async def test_search(self):
        """Test similarity search"""
        engine = SimilarityEngine()
        
        # Build index
        embeddings = np.random.rand(10, 128).astype(np.float32)
        await engine.build_index(embeddings, "test_index")
        
        # Search
        query = np.random.rand(128).astype(np.float32)
        results = await engine.search(query, "test_index", k=5)
        
        assert len(results) <= 5
        assert all(hasattr(r, 'index') and hasattr(r, 'score') for r in results)


class TestContentMesh:
    """Test content mesh algorithm"""
    
    def test_add_node(self):
        """Test adding nodes to mesh"""
        similarity_engine = Mock(spec=SimilarityEngine)
        mesh = ContentMesh(similarity_engine)
        
        from src.ml.content_mesh import ContentNode
        node = ContentNode(
            id="test_1",
            title="Test Node",
            content="Test content",
            embedding=np.random.rand(128),
            metadata={}
        )
        
        mesh.add_node(node)
        
        assert "test_1" in mesh.nodes
        assert mesh.graph.has_node("test_1")
    
    def test_find_content_gaps(self):
        """Test gap identification in mesh"""
        similarity_engine = Mock(spec=SimilarityEngine)
        mesh = ContentMesh(similarity_engine)
        
        # Add some nodes
        from src.ml.content_mesh import ContentNode
        for i in range(3):
            node = ContentNode(
                id=f"test_{i}",
                title=f"Test Node {i}",
                content=f"Test content {i}",
                embedding=np.random.rand(128),
                metadata={}
            )
            mesh.add_node(node)
        
        gaps = mesh.find_content_gaps()
        
        assert isinstance(gaps, list)


class TestOptimizationEngine:
    """Test optimization suggestions engine"""
    
    @pytest.mark.asyncio
    async def test_analyze_readability(self):
        """Test readability analysis"""
        mock_model_manager = Mock()
        mock_similarity = Mock()
        mock_gap_analysis = Mock()
        
        engine = OptimizationEngine(mock_model_manager, mock_similarity, mock_gap_analysis)
        
        content = "This is a very long and complex sentence that contains multiple clauses and subclauses which makes it difficult to read and understand for the average reader who might not have advanced reading skills."
        
        suggestions = await engine._analyze_readability(content, Mock(target_reading_level=8))
        
        assert len(suggestions) > 0
        assert any(s.category == "readability" for s in suggestions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])