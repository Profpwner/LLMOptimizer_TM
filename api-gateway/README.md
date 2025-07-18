# API Gateway Service

The API Gateway is the main entry point for all client requests to the LLMOptimizer platform. It handles routing, authentication, rate limiting, and request/response transformation.

## Features

- Request routing to microservices
- Authentication and authorization
- Rate limiting and throttling
- Request/response logging
- Health checks and monitoring
- CORS handling
- API versioning
- Metrics collection (Prometheus)

## Technology Stack

- **Language**: Go 1.21
- **Framework**: Gin Web Framework
- **Monitoring**: Prometheus metrics
- **Logging**: Zap structured logging

## API Endpoints

### Health & Monitoring
- `GET /health` - Health check endpoint
- `GET /ready` - Readiness check (validates all dependent services)
- `GET /metrics` - Prometheus metrics

### API Routes (v1)

#### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - User logout

#### Content Management (`/api/v1/content`)
- `GET /api/v1/content` - List content
- `POST /api/v1/content` - Create content
- `GET /api/v1/content/:id` - Get content by ID
- `PUT /api/v1/content/:id` - Update content
- `DELETE /api/v1/content/:id` - Delete content

#### Analytics (`/api/v1/analytics`)
- `GET /api/v1/analytics/dashboard` - Dashboard data
- `GET /api/v1/analytics/reports` - Analytics reports
- `POST /api/v1/analytics/track` - Track events

#### Machine Learning (`/api/v1/ml`)
- `POST /api/v1/ml/optimize` - Optimize content
- `POST /api/v1/ml/analyze` - Analyze content
- `GET /api/v1/ml/models` - List available models

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8080` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `VERSION` | Service version | `1.0.0` |
| `LOG_LEVEL` | Logging level | `info` |

## Development

### Prerequisites
- Go 1.21 or higher
- Docker (for containerized development)

### Running Locally

```bash
# Install dependencies
go mod download

# Run the service
go run main.go

# Or with environment variables
PORT=8080 ENVIRONMENT=development go run main.go
```

### Building

```bash
# Build binary
go build -o api-gateway .

# Build Docker image
docker build -t llmoptimizer/api-gateway:latest .
```

### Testing

```bash
# Run tests
go test ./...

# Run tests with coverage
go test -cover ./...
```

## Deployment

The service is designed to run in Kubernetes. See the infrastructure/k8s directory for deployment manifests.

## Monitoring

- Health endpoint: `http://localhost:8080/health`
- Metrics endpoint: `http://localhost:8080/metrics`
- Logs are structured JSON format for easy parsing

## Security

- All endpoints except health checks require authentication
- CORS is configured for cross-origin requests
- Rate limiting is applied per IP address
- All sensitive data is encrypted in transit