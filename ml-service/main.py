import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import asyncio

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest
from pythonjsonlogger import jsonlogger
from bson import ObjectId
import numpy as np
import uvicorn

# Import semantic saturation components
from src.ml import (
    SemanticSaturationController,
    SemanticAnalysisRequest,
    get_model_manager
)

# Configure logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Database connections
mongo_client: Optional[AsyncIOMotorClient] = None
redis_client: Optional[redis.Redis] = None

# ML Models placeholder (in production, load actual models)
models = {}

# Semantic saturation controller
semantic_controller: Optional[SemanticSaturationController] = None

# Metrics
optimization_requests = Counter('ml_optimization_requests_total', 'Total optimization requests')
analysis_requests = Counter('ml_analysis_requests_total', 'Total analysis requests')
model_inference_duration = Histogram('ml_model_inference_duration_seconds', 'Model inference duration')

# Enums
class OptimizationGoal(str, Enum):
    ENGAGEMENT = "engagement"
    CONVERSION = "conversion"
    SEO = "seo"
    READABILITY = "readability"
    BRAND_VOICE = "brand_voice"

class ModelType(str, Enum):
    GPT3 = "gpt3"
    GPT4 = "gpt4"
    CLAUDE = "claude"
    LLAMA = "llama"
    CUSTOM = "custom"

# Models
class OptimizationRequest(BaseModel):
    content: str = Field(..., min_length=10)
    content_type: str
    optimization_goals: List[OptimizationGoal]
    target_audience: Optional[str] = None
    keywords: Optional[List[str]] = []
    tone: Optional[str] = "professional"
    max_length: Optional[int] = None
    model_type: Optional[ModelType] = ModelType.GPT4

class OptimizationResponse(BaseModel):
    request_id: str
    original_content: str
    optimized_content: str
    optimization_score: float
    improvements: List[str]
    metrics: Dict[str, float]
    model_used: str
    processing_time: float

class AnalysisRequest(BaseModel):
    content: str
    analyze_for: List[str] = ["readability", "seo", "engagement", "sentiment"]

class AnalysisResponse(BaseModel):
    request_id: str
    content_length: int
    readability_score: float
    seo_score: float
    sentiment: Dict[str, float]
    keywords: List[str]
    suggestions: List[str]

class ModelInfo(BaseModel):
    model_id: str
    model_type: ModelType
    name: str
    description: str
    capabilities: List[str]
    is_available: bool
    average_latency_ms: float

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global mongo_client, redis_client
    
    # MongoDB connection
    mongo_url = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
    mongo_client = AsyncIOMotorClient(mongo_url)
    app.state.db = mongo_client.llmoptimizer
    
    # Redis connection
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = await redis.from_url(redis_url)
    app.state.redis = redis_client
    
    # Initialize semantic saturation controller
    logger.info("Initializing semantic saturation controller...")
    global semantic_controller
    semantic_controller = SemanticSaturationController(
        redis_client=redis_client,
        mongodb_client=mongo_client
    )
    await semantic_controller.initialize()
    
    # Load ML models (placeholder)
    logger.info("Loading ML models...")
    # In production, load actual models here
    models["default"] = {"type": "mock", "loaded": True}
    
    logger.info("ML service started")
    yield
    
    # Shutdown
    if semantic_controller:
        semantic_controller.cleanup()
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()
    logger.info("ML service stopped")

# Create FastAPI app
app = FastAPI(
    title="ML Service",
    description="Machine Learning service for content optimization",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock authentication dependency
async def get_current_user():
    # TODO: Implement proper JWT validation
    return {"id": "user123", "email": "user@example.com"}

# Helper functions
async def mock_optimize_content(
    content: str,
    optimization_goals: List[OptimizationGoal],
    **kwargs
) -> Dict:
    """Mock content optimization (replace with actual ML model)"""
    # Simulate processing time
    await asyncio.sleep(0.5)
    
    # Mock optimization
    optimized = content
    improvements = []
    
    if OptimizationGoal.READABILITY in optimization_goals:
        optimized = optimized.replace("utilize", "use").replace("implement", "do")
        improvements.append("Simplified complex words for better readability")
    
    if OptimizationGoal.SEO in optimization_goals:
        keywords = kwargs.get("keywords", [])
        if keywords:
            improvements.append(f"Incorporated keywords: {', '.join(keywords[:3])}")
    
    if OptimizationGoal.ENGAGEMENT in optimization_goals:
        optimized = f"📊 {optimized}\n\n💡 Key Takeaway: [Your main point here]"
        improvements.append("Added engagement elements")
    
    # Calculate mock scores
    optimization_score = np.random.uniform(70, 95)
    metrics = {
        "readability": np.random.uniform(60, 90),
        "seo_score": np.random.uniform(65, 85),
        "engagement_potential": np.random.uniform(70, 90),
        "originality": np.random.uniform(80, 95)
    }
    
    return {
        "optimized_content": optimized,
        "optimization_score": optimization_score,
        "improvements": improvements,
        "metrics": metrics
    }

async def mock_analyze_content(content: str, analyze_for: List[str]) -> Dict:
    """Mock content analysis (replace with actual ML model)"""
    # Simulate processing time
    await asyncio.sleep(0.3)
    
    # Mock analysis
    word_count = len(content.split())
    char_count = len(content)
    
    results = {
        "content_length": char_count,
        "readability_score": min(100, 110 - (char_count / word_count)),
        "seo_score": np.random.uniform(60, 85),
        "sentiment": {
            "positive": np.random.uniform(0.4, 0.7),
            "neutral": np.random.uniform(0.2, 0.4),
            "negative": np.random.uniform(0.05, 0.2)
        },
        "keywords": ["optimization", "content", "AI", "performance", "engagement"][:3],
        "suggestions": []
    }
    
    # Generate suggestions
    if results["readability_score"] < 70:
        results["suggestions"].append("Consider using shorter sentences for better readability")
    
    if results["seo_score"] < 70:
        results["suggestions"].append("Add more relevant keywords and meta descriptions")
    
    if word_count < 300:
        results["suggestions"].append("Consider expanding content for better SEO performance")
    
    return results

# Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ml-service",
        "version": "1.0.0",
        "models_loaded": len(models)
    }

@app.get("/ready")
async def readiness_check():
    try:
        # Check MongoDB
        await app.state.db.command("ping")
        # Check Redis
        await app.state.redis.ping()
        # Check models
        if not models:
            raise Exception("No models loaded")
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "error": str(e)}
        )

@app.post("/optimize", response_model=OptimizationResponse)
async def optimize_content(
    request: OptimizationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    optimization_requests.inc()
    start_time = datetime.utcnow()
    
    # Create request record
    request_dict = {
        "user_id": current_user["id"],
        "content": request.content,
        "content_type": request.content_type,
        "optimization_goals": request.optimization_goals,
        "target_audience": request.target_audience,
        "keywords": request.keywords,
        "tone": request.tone,
        "model_type": request.model_type,
        "status": "processing",
        "created_at": start_time
    }
    
    result = await app.state.db.ml_requests.insert_one(request_dict)
    request_id = str(result.inserted_id)
    
    # Perform optimization
    with model_inference_duration.time():
        optimization_result = await mock_optimize_content(
            request.content,
            request.optimization_goals,
            keywords=request.keywords,
            target_audience=request.target_audience,
            tone=request.tone
        )
    
    end_time = datetime.utcnow()
    processing_time = (end_time - start_time).total_seconds()
    
    # Update request record
    await app.state.db.ml_requests.update_one(
        {"_id": result.inserted_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": end_time,
                "processing_time": processing_time,
                "optimization_score": optimization_result["optimization_score"]
            }
        }
    )
    
    # Cache result
    response = OptimizationResponse(
        request_id=request_id,
        original_content=request.content,
        optimized_content=optimization_result["optimized_content"],
        optimization_score=optimization_result["optimization_score"],
        improvements=optimization_result["improvements"],
        metrics=optimization_result["metrics"],
        model_used=request.model_type,
        processing_time=processing_time
    )
    
    await app.state.redis.setex(
        f"optimization:{request_id}",
        3600,  # 1 hour cache
        response.model_dump_json()
    )
    
    logger.info(f"Content optimized: {request_id} for user {current_user['id']}")
    return response

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_content(
    request: AnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    analysis_requests.inc()
    start_time = datetime.utcnow()
    
    # Create request record
    request_dict = {
        "user_id": current_user["id"],
        "content": request.content,
        "analyze_for": request.analyze_for,
        "created_at": start_time
    }
    
    result = await app.state.db.ml_analysis.insert_one(request_dict)
    request_id = str(result.inserted_id)
    
    # Perform analysis
    with model_inference_duration.time():
        analysis_result = await mock_analyze_content(
            request.content,
            request.analyze_for
        )
    
    response = AnalysisResponse(
        request_id=request_id,
        **analysis_result
    )
    
    # Cache result
    await app.state.redis.setex(
        f"analysis:{request_id}",
        3600,  # 1 hour cache
        response.model_dump_json()
    )
    
    logger.info(f"Content analyzed: {request_id} for user {current_user['id']}")
    return response

@app.get("/models", response_model=List[ModelInfo])
async def list_models(current_user: dict = Depends(get_current_user)):
    """List available ML models"""
    available_models = [
        ModelInfo(
            model_id="gpt4-turbo",
            model_type=ModelType.GPT4,
            name="GPT-4 Turbo",
            description="Latest GPT-4 model with improved performance",
            capabilities=["optimization", "analysis", "generation"],
            is_available=True,
            average_latency_ms=1200
        ),
        ModelInfo(
            model_id="claude-2",
            model_type=ModelType.CLAUDE,
            name="Claude 2",
            description="Anthropic's Claude 2 for nuanced content",
            capabilities=["optimization", "analysis"],
            is_available=True,
            average_latency_ms=1500
        ),
        ModelInfo(
            model_id="llama-70b",
            model_type=ModelType.LLAMA,
            name="LLaMA 70B",
            description="Meta's LLaMA model for efficient processing",
            capabilities=["optimization", "analysis"],
            is_available=False,
            average_latency_ms=800
        )
    ]
    
    return available_models

@app.get("/optimization/{request_id}")
async def get_optimization_result(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get optimization result by request ID"""
    # Try cache first
    cached = await app.state.redis.get(f"optimization:{request_id}")
    if cached:
        return OptimizationResponse.model_validate_json(cached)
    
    # Get from database
    try:
        request = await app.state.db.ml_requests.find_one({
            "_id": ObjectId(request_id),
            "user_id": current_user["id"]
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request ID"
        )
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Optimization request not found"
        )
    
    if request["status"] != "completed":
        return {"status": request["status"], "message": "Optimization still processing"}
    
    # Return stored result (simplified for this example)
    return {
        "request_id": request_id,
        "status": "completed",
        "optimization_score": request.get("optimization_score", 0)
    }

# New Semantic Analysis Models
class SemanticAnalysisRequestModel(BaseModel):
    content_items: List[Dict[str, Any]] = Field(..., min_items=1)
    target_keywords: List[str] = Field(..., min_items=1)
    reference_topics: Optional[List[str]] = None
    competitor_content: Optional[List[Dict[str, Any]]] = None
    optimization_goals: Optional[List[str]] = None
    analysis_config: Optional[Dict[str, Any]] = None

class SemanticAnalysisResponseModel(BaseModel):
    request_id: str
    timestamp: str
    content_mesh: Dict[str, Any]
    semantic_gaps: List[Dict[str, Any]]
    optimization_suggestions: List[Dict[str, Any]]
    visualizations: Dict[str, Any]
    metrics: Dict[str, float]
    processing_time: float

# Semantic Analysis Endpoints
@app.post("/semantic-analysis", response_model=SemanticAnalysisResponseModel)
async def perform_semantic_analysis(
    request: SemanticAnalysisRequestModel,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Perform comprehensive semantic saturation analysis"""
    if not semantic_controller:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic analysis service not initialized"
        )
    
    # Create analysis request
    analysis_request = SemanticAnalysisRequest(
        content_items=request.content_items,
        target_keywords=request.target_keywords,
        reference_topics=request.reference_topics,
        competitor_content=request.competitor_content,
        optimization_goals=request.optimization_goals,
        analysis_config=request.analysis_config
    )
    
    try:
        # Perform analysis
        result = await semantic_controller.analyze_content(analysis_request)
        
        # Convert to response model
        response = SemanticAnalysisResponseModel(
            request_id=result.request_id,
            timestamp=result.timestamp.isoformat(),
            content_mesh=result.content_mesh,
            semantic_gaps=result.semantic_gaps,
            optimization_suggestions=result.optimization_suggestions,
            visualizations=result.visualizations,
            metrics=result.metrics,
            processing_time=result.processing_time
        )
        
        # Log analysis
        logger.info(f"Semantic analysis completed: {result.request_id} for user {current_user['id']}")
        
        return response
        
    except Exception as e:
        logger.error(f"Semantic analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

@app.get("/semantic-analysis/{request_id}")
async def get_semantic_analysis_result(
    request_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get semantic analysis result by request ID"""
    if not semantic_controller:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic analysis service not initialized"
        )
    
    result = await semantic_controller.get_analysis_result(request_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found"
        )
    
    return result

@app.post("/embeddings/generate")
async def generate_embeddings(
    texts: List[str] = Field(..., min_items=1, max_items=100),
    model_type: str = "default",
    current_user: dict = Depends(get_current_user)
):
    """Generate embeddings for given texts"""
    if not semantic_controller:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not initialized"
        )
    
    try:
        # Generate embeddings
        embeddings = await semantic_controller.embedding_pipeline.generate_embeddings(
            texts,
            config={"model_type": model_type}
        )
        
        # Convert to list format
        embedding_list = [emb.tolist() for emb in embeddings]
        
        return {
            "embeddings": embedding_list,
            "dimensions": len(embedding_list[0]) if embedding_list else 0,
            "count": len(embedding_list)
        }
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}"
        )

@app.post("/similarity/search")
async def similarity_search(
    query: str,
    corpus: List[str] = Field(..., min_items=1, max_items=1000),
    top_k: int = Field(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Perform similarity search in a corpus"""
    if not semantic_controller:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Similarity service not initialized"
        )
    
    try:
        # Generate embeddings for corpus
        corpus_embeddings = await semantic_controller.embedding_pipeline.generate_embeddings(corpus)
        
        # Generate query embedding
        query_embedding = (await semantic_controller.embedding_pipeline.generate_embeddings([query]))[0]
        
        # Build index
        await semantic_controller.similarity_engine.build_index(
            np.array(corpus_embeddings),
            "temp_search",
            metadata=[{"text": text, "index": i} for i, text in enumerate(corpus)]
        )
        
        # Search
        results = await semantic_controller.similarity_engine.search(
            query_embedding,
            "temp_search",
            k=top_k
        )
        
        # Format results
        search_results = []
        for result in results:
            search_results.append({
                "text": corpus[result.index],
                "score": result.score,
                "index": result.index
            })
        
        return {
            "query": query,
            "results": search_results,
            "total_results": len(search_results)
        }
        
    except Exception as e:
        logger.error(f"Similarity search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Similarity search failed: {str(e)}"
        )

@app.get("/metrics")
async def metrics():
    return generate_latest()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development"
    )