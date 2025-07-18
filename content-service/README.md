# Content Service

The Content Service manages all content-related operations for the LLMOptimizer platform, including creation, storage, retrieval, and optimization tracking.

## Features

- CRUD operations for content items
- Content categorization by type
- Status management (draft, published, archived)
- Keyword and metadata storage
- Content caching with Redis
- Pagination support
- User-specific content isolation
- Prometheus metrics
- Structured JSON logging

## Technology Stack

- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: MongoDB
- **Cache**: Redis
- **API Documentation**: OpenAPI/Swagger

## Content Types Supported

- Article
- Blog Post
- Product Description
- Social Media
- Email
- Landing Page

## API Endpoints

### Content Management
- `POST /` - Create new content
- `GET /` - List user's content (with pagination and filters)
- `GET /{content_id}` - Get specific content
- `PUT /{content_id}` - Update content
- `DELETE /{content_id}` - Delete content

### Health & Monitoring
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics

## Request/Response Examples

### Create Content
```json
POST /
{
  "title": "My Blog Post",
  "content_type": "blog_post",
  "original_content": "This is the original content...",
  "target_audience": "Tech professionals",
  "keywords": ["AI", "optimization", "content"],
  "metadata": {
    "category": "technology",
    "tags": ["ai", "ml"]
  }
}
```

### List Content
```
GET /?page=1&page_size=10&status=published&content_type=blog_post
```

### Update Content
```json
PUT /{content_id}
{
  "title": "Updated Title",
  "optimized_content": "This is the AI-optimized content...",
  "status": "published"
}
```

## Data Models

### Content Schema
```json
{
  "id": "string",
  "user_id": "string",
  "title": "string",
  "content_type": "string",
  "original_content": "string",
  "optimized_content": "string",
  "target_audience": "string",
  "keywords": ["string"],
  "metadata": {},
  "status": "draft|published|archived",
  "optimization_score": 0.0,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `8000` |
| `MONGODB_URL` | MongoDB connection string | `mongodb://mongodb:27017` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `CACHE_TTL` | Redis cache TTL in seconds | `3600` |

## Development

### Prerequisites
- Python 3.11+
- MongoDB
- Redis

### Running Locally

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

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

## Performance Considerations

- Content is cached in Redis for 1 hour by default
- MongoDB indexes on user_id, status, and created_at for fast queries
- Pagination is enforced with a maximum page size of 100 items

## Integration with Other Services

- **Auth Service**: Validates user tokens for all operations
- **ML Service**: Sends content for optimization
- **Analytics Service**: Tracks content performance metrics

## Monitoring

- Health endpoint: `http://localhost:8000/health`
- Metrics endpoint: `http://localhost:8000/metrics`
- Key metrics tracked:
  - Total content created
  - Total content updated
  - Total content deleted
  - Request duration histogram