# LLMOptimizer - Microservices Setup Guide

This guide focuses on the microservices architecture implementation for the LLMOptimizer platform.

## Architecture Overview

The platform is built using a microservices architecture with the following services:

### Services

1. **API Gateway** (Go/Gin) - Port 8080
   - Main entry point for all client requests
   - Request routing and load balancing
   - Authentication middleware
   - Rate limiting and monitoring

2. **Auth Service** (Python/FastAPI) - Port 8001
   - User registration and authentication
   - JWT token management
   - Session management with Redis

3. **Content Service** (Python/FastAPI) - Port 8002
   - Content CRUD operations
   - Content optimization tracking
   - MongoDB for document storage

4. **Analytics Service** (Python/FastAPI) - Port 8003
   - Event tracking and analytics
   - Real-time metrics aggregation
   - Dashboard data and reports

5. **ML Service** (Python/FastAPI) - Port 8004
   - Content optimization using LLMs
   - Content analysis (SEO, readability)
   - Model management and inference

### Databases

- **PostgreSQL**: Structured data (future use)
- **MongoDB**: Document storage for content and analytics
- **Redis**: Caching and session management

## Quick Start with Docker Compose

### Prerequisites
- Docker and Docker Compose
- 8GB RAM minimum
- 20GB free disk space

### Steps

1. **Clone and setup environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start all services**:
   ```bash
   docker-compose up -d
   ```

3. **Verify services are running**:
   ```bash
   # Check API Gateway health
   curl http://localhost:8080/health

   # Check all services readiness
   curl http://localhost:8080/ready
   ```

4. **Access service documentation**:
   - API Gateway: http://localhost:8080/docs
   - Auth Service: http://localhost:8001/docs  
   - Content Service: http://localhost:8002/docs
   - Analytics Service: http://localhost:8003/docs
   - ML Service: http://localhost:8004/docs

## Development Workflow

### Running Services Individually

**API Gateway (Go)**:
```bash
cd api-gateway
go mod download
PORT=8080 go run main.go
```

**Python Services**:
```bash
cd [service-name]
pip install -r requirements.txt
python main.py
```

### Testing

**Run tests for a specific service**:
```bash
# Go tests
cd api-gateway
go test ./...

# Python tests
cd [service-name]
pytest
```

## API Examples

### Authentication Flow

1. **Register a user**:
   ```bash
   curl -X POST http://localhost:8080/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "email": "user@example.com",
       "password": "securepassword",
       "full_name": "John Doe"
     }'
   ```

2. **Login**:
   ```bash
   curl -X POST http://localhost:8080/api/v1/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=securepassword"
   ```

3. **Use the token for authenticated requests**:
   ```bash
   curl -X GET http://localhost:8080/api/v1/content \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
   ```

### Content Management

**Create content**:
```bash
curl -X POST http://localhost:8080/api/v1/content \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Article",
    "content_type": "blog_post",
    "original_content": "This is my content...",
    "keywords": ["AI", "optimization"]
  }'
```

**Optimize content**:
```bash
curl -X POST http://localhost:8080/api/v1/ml/optimize \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Original content to optimize...",
    "content_type": "blog_post",
    "optimization_goals": ["engagement", "seo"],
    "target_audience": "tech professionals"
  }'
```

## Kubernetes Deployment

### Deploy to Kubernetes

1. **Create namespace**:
   ```bash
   kubectl apply -f infrastructure/k8s/namespace.yaml
   ```

2. **Apply all manifests**:
   ```bash
   kubectl apply -f infrastructure/k8s/
   ```

3. **Check deployment status**:
   ```bash
   kubectl get pods -n llmoptimizer
   kubectl get services -n llmoptimizer
   ```

## Monitoring

Each service exposes:
- `/health` - Basic health check
- `/ready` - Readiness check (includes dependency checks)
- `/metrics` - Prometheus metrics

### View logs:
```bash
# Docker Compose
docker-compose logs -f [service-name]

# Kubernetes
kubectl logs -f deployment/[service-name] -n llmoptimizer
```

## Troubleshooting

### Service won't start
1. Check logs: `docker-compose logs [service-name]`
2. Verify environment variables in `.env`
3. Ensure ports are not already in use

### Database connection issues
1. Verify database containers are running: `docker-compose ps`
2. Check connection strings in `.env`
3. Ensure databases are initialized

### API Gateway can't reach services
1. Verify all services are healthy: `curl http://localhost:8080/ready`
2. Check Docker network: `docker network ls`
3. Ensure service URLs are correct in environment variables

## CI/CD

The project includes GitHub Actions workflows for:
- Testing all services
- Building Docker images
- Deploying to Kubernetes

See `.github/workflows/ci-cd.yml` for details.

## Next Steps

1. Configure your ML API keys in `.env`
2. Set up monitoring with Prometheus/Grafana
3. Configure ingress for production deployment
4. Set up SSL/TLS certificates
5. Implement service mesh (optional)

For more details, see the main [README.md](README.md).