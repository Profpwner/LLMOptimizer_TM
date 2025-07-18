# Analytics Service

The Analytics Service tracks user interactions, content performance, and generates insights for the LLMOptimizer platform.

## Features

- Event tracking (page views, clicks, conversions, engagement)
- Real-time metrics aggregation
- Dashboard metrics API
- Custom report generation
- Content performance analysis
- Conversion tracking
- Revenue tracking
- Time-series data analysis
- Prometheus metrics
- Structured JSON logging

## Technology Stack

- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: MongoDB
- **Cache**: Redis
- **Data Analysis**: Pandas, NumPy

## Event Types

- `page_view` - Page view tracking
- `content_view` - Content item viewed
- `content_optimized` - Content optimization completed
- `conversion` - Conversion event (with revenue tracking)
- `engagement` - User engagement with content
- `click` - Click tracking

## API Endpoints

### Event Tracking
- `POST /track` - Track an analytics event

### Analytics & Reporting
- `GET /dashboard` - Get dashboard metrics
- `POST /reports` - Generate custom analytics report

### Health & Monitoring
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics

## Request/Response Examples

### Track Event
```json
POST /track
{
  "event_type": "content_view",
  "content_id": "123456",
  "user_id": "user123",
  "session_id": "session456",
  "properties": {
    "source": "homepage",
    "device": "mobile"
  }
}
```

### Track Conversion
```json
POST /track
{
  "event_type": "conversion",
  "content_id": "123456",
  "user_id": "user123",
  "session_id": "session456",
  "properties": {
    "revenue": 99.99,
    "product": "premium_plan"
  }
}
```

### Dashboard Metrics
```
GET /dashboard?days=7
```

Response:
```json
{
  "total_views": 1500,
  "total_clicks": 450,
  "total_conversions": 45,
  "avg_engagement_rate": 35.5,
  "avg_optimization_score": 78.2,
  "total_revenue": 4499.55,
  "top_content": [
    {
      "content_id": "123",
      "views": 250,
      "conversions": 12,
      "conversion_rate": 4.8
    }
  ],
  "metrics_by_day": [...]
}
```

### Generate Report
```json
POST /reports
{
  "start_date": "2024-01-01T00:00:00",
  "end_date": "2024-01-31T23:59:59",
  "metrics": ["views", "conversions", "revenue"],
  "group_by": "day",
  "content_ids": ["123", "456"]
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `8000` |
| `MONGODB_URL` | MongoDB connection string | `mongodb://mongodb:27017` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `ENVIRONMENT` | Environment (development/production) | `development` |

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

## Data Storage

### MongoDB Collections

- `analytics_events` - All tracked events
- `analytics_reports` - Generated reports

### Redis Keys

- `metrics:{user_id}:{date}` - Daily aggregated metrics

## Performance Considerations

- Events are indexed by user_id, content_id, timestamp, and event_type
- Real-time metrics are cached in Redis
- Dashboard queries are optimized with MongoDB aggregation pipelines
- Pandas is used for complex data analysis

## Integration with Other Services

- **Auth Service**: Validates user tokens
- **Content Service**: Links analytics to content items
- **ML Service**: Provides optimization scores

## Monitoring

- Health endpoint: `http://localhost:8000/health`
- Metrics endpoint: `http://localhost:8000/metrics`
- Key metrics tracked:
  - Total events tracked
  - Total reports generated
  - Request duration histogram