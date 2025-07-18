.PHONY: help build up down logs ps test clean

# Default target
help:
	@echo "LLMOptimizer Microservices - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  help        Show this help message"
	@echo "  build       Build all Docker images"
	@echo "  up          Start all services with docker-compose"
	@echo "  down        Stop all services"
	@echo "  logs        Show logs from all services"
	@echo "  ps          Show running containers"
	@echo "  test        Run tests for all services"
	@echo "  clean       Clean up containers, volumes, and images"
	@echo ""
	@echo "Service-specific commands:"
	@echo "  build-api   Build API Gateway image"
	@echo "  build-auth  Build Auth Service image"
	@echo "  build-content Build Content Service image"
	@echo "  build-analytics Build Analytics Service image"
	@echo "  build-ml    Build ML Service image"
	@echo ""
	@echo "  test-api    Run API Gateway tests"
	@echo "  test-auth   Run Auth Service tests"
	@echo "  test-content Run Content Service tests"
	@echo "  test-analytics Run Analytics Service tests"
	@echo "  test-ml     Run ML Service tests"
	@echo ""
	@echo "  logs-api    Show API Gateway logs"
	@echo "  logs-auth   Show Auth Service logs"
	@echo "  logs-content Show Content Service logs"
	@echo "  logs-analytics Show Analytics Service logs"
	@echo "  logs-ml     Show ML Service logs"

# Build all services
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Services are starting. Check health at http://localhost:8080/health"

# Stop all services
down:
	docker-compose down

# Show logs from all services
logs:
	docker-compose logs -f

# Show running containers
ps:
	docker-compose ps

# Run all tests
test: test-api test-auth test-content test-analytics test-ml

# Clean up everything
clean:
	docker-compose down -v
	docker system prune -f

# Service-specific build commands
build-api:
	docker-compose build api-gateway

build-auth:
	docker-compose build auth-service

build-content:
	docker-compose build content-service

build-analytics:
	docker-compose build analytics-service

build-ml:
	docker-compose build ml-service

# Service-specific test commands
test-api:
	cd api-gateway && go test ./...

test-auth:
	cd auth-service && python -m pytest

test-content:
	cd content-service && python -m pytest

test-analytics:
	cd analytics-service && python -m pytest

test-ml:
	cd ml-service && python -m pytest

# Service-specific log commands
logs-api:
	docker-compose logs -f api-gateway

logs-auth:
	docker-compose logs -f auth-service

logs-content:
	docker-compose logs -f content-service

logs-analytics:
	docker-compose logs -f analytics-service

logs-ml:
	docker-compose logs -f ml-service

# Database specific commands
db-mongo:
	docker-compose exec mongodb mongosh -u admin -p admin123

db-redis:
	docker-compose exec redis redis-cli

db-postgres:
	docker-compose exec postgres psql -U llmoptimizer -d llmoptimizer

# Development shortcuts
dev: up logs

restart:
	docker-compose restart

reload: down up

# Health checks
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8080/health | jq . || echo "API Gateway is not responding"
	@echo ""
	@echo "Checking service readiness..."
	@curl -s http://localhost:8080/ready | jq . || echo "Some services may not be ready"

# Initialize development environment
init:
	@echo "Initializing development environment..."
	@cp -n .env.example .env || true
	@echo "Environment file ready. Please edit .env with your configuration."
	@echo "Run 'make up' to start services."