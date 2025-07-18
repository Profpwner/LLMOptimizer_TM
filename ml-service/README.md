# ML Service

The Machine Learning Service provides AI-powered content optimization and analysis capabilities for the LLMOptimizer platform.

## Features

- Content optimization using multiple LLM models
- Content analysis (readability, SEO, sentiment)
- Multiple optimization goals support
- Model selection and management
- Asynchronous processing
- Result caching
- Prometheus metrics
- Structured JSON logging

## Technology Stack

- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: MongoDB
- **Cache**: Redis
- **ML Libraries**: Transformers, PyTorch, Scikit-learn
- **NLP**: NLTK, spaCy, Sentence Transformers

## Optimization Goals

- `engagement` - Optimize for user engagement
- `conversion` - Optimize for conversion rates
- `seo` - Optimize for search engines
- `readability` - Improve readability scores
- `brand_voice` - Maintain brand consistency

## Supported Models

- GPT-4 Turbo
- Claude 2
- LLaMA 70B
- Custom fine-tuned models

## API Endpoints

### Content Operations
- `POST /optimize` - Optimize content
- `POST /analyze` - Analyze content
- `GET /optimization/{request_id}` - Get optimization result

### Model Management
- `GET /models` - List available models

### Health & Monitoring
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics

## Request/Response Examples

### Semantic Analysis (New)
```json
POST /semantic-analysis
{
  "content_items": [
    {
      "id": "1",
      "title": "Introduction to AI",
      "content": "Content text...",
      "metadata": {}
    }
  ],
  "target_keywords": ["AI", "machine learning"],
  "reference_topics": ["deep learning", "neural networks"],
  "competitor_content": []
}
```

Response:
```json
{
  "request_id": "sem_1234567890",
  "timestamp": "2024-01-15T10:30:00Z",
  "content_mesh": {
    "nodes": 10,
    "edges": 25,
    "communities": 3,
    "density": 0.278,
    "gaps": [...]
  },
  "semantic_gaps": [
    {
      "id": "gap_1",
      "type": "missing_topic",
      "description": "Poor coverage of reference topic: neural networks",
      "severity": 0.85,
      "recommendations": [...]
    }
  ],
  "optimization_suggestions": [
    {
      "category": "readability",
      "priority": "high",
      "description": "Content reading level exceeds target",
      "implementation": "Simplify complex sentences"
    }
  ],
  "visualizations": {
    "network_3d": {...},
    "gap_analysis": {...}
  },
  "metrics": {
    "semantic_health_score": 0.72,
    "content_density": 0.278,
    "avg_gap_severity": 0.65
  },
  "processing_time": 3.45
}
```

### Optimize Content
```json
POST /optimize
{
  "content": "Your content to optimize...",
  "content_type": "blog_post",
  "optimization_goals": ["engagement", "seo"],
  "target_audience": "tech professionals",
  "keywords": ["AI", "optimization", "content"],
  "tone": "professional",
  "model_type": "gpt4"
}
```

Response:
```json
{
  "request_id": "507f1f77bcf86cd799439011",
  "original_content": "Your content to optimize...",
  "optimized_content": "Your professionally optimized content...",
  "optimization_score": 87.5,
  "improvements": [
    "Simplified complex words for better readability",
    "Incorporated keywords: AI, optimization, content"
  ],
  "metrics": {
    "readability": 82.3,
    "seo_score": 78.9,
    "engagement_potential": 85.2,
    "originality": 91.5
  },
  "model_used": "gpt4",
  "processing_time": 2.3
}
```

### Analyze Content
```json
POST /analyze
{
  "content": "Content to analyze...",
  "analyze_for": ["readability", "seo", "engagement", "sentiment"]
}
```

Response:
```json
{
  "request_id": "507f1f77bcf86cd799439012",
  "content_length": 500,
  "readability_score": 75.2,
  "seo_score": 68.5,
  "sentiment": {
    "positive": 0.65,
    "neutral": 0.30,
    "negative": 0.05
  },
  "keywords": ["optimization", "content", "AI"],
  "suggestions": [
    "Consider using shorter sentences for better readability",
    "Add more relevant keywords and meta descriptions"
  ]
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `8000` |
| `MONGODB_URL` | MongoDB connection string | `mongodb://mongodb:27017` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `MODEL_CACHE_DIR` | Directory for model cache | `/app/models` |
| `MAX_CONTENT_LENGTH` | Maximum content length | `50000` |

## Development

### Prerequisites
- Python 3.11+
- MongoDB
- Redis
- CUDA-capable GPU (optional, for faster inference)

### Running Locally

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download required NLTK data
python -m nltk.downloader punkt stopwords wordnet

# Download spaCy model
python -m spacy download en_core_web_sm

# Run the service
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=.
```

## Model Management

### Adding New Models

1. Add model configuration to `models.json`
2. Implement model loader in `models/loaders.py`
3. Add optimization logic in `models/optimizers.py`
4. Update available models endpoint

### Model Caching

- Models are cached in Redis after first load
- Cache TTL: 24 hours
- Automatic cache invalidation on model update

## Performance Optimization

- Batch processing for multiple requests
- Model quantization for faster inference
- Result caching to avoid redundant processing
- Async processing for long-running tasks

## Security Considerations

- Input validation and sanitization
- Content length limits
- Rate limiting per user
- Model access control

## Monitoring

- Health endpoint: `http://localhost:8000/health`
- Metrics endpoint: `http://localhost:8000/metrics`
- Key metrics tracked:
  - Total optimization requests
  - Total analysis requests
  - Model inference duration
  - Cache hit rates