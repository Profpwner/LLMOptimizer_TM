# Makefile for Auth Service

.PHONY: help install test test-unit test-integration test-security test-coverage clean lint format check-format type-check security-check run dev migrate docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  install          Install dependencies"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-security   Run security tests only"
	@echo "  test-coverage   Run tests with coverage report"
	@echo "  lint            Run linting"
	@echo "  format          Format code"
	@echo "  check-format    Check code formatting"
	@echo "  type-check      Run type checking"
	@echo "  security-check  Run security checks"
	@echo "  clean           Clean up generated files"
	@echo "  run             Run the service"
	@echo "  dev             Run in development mode"
	@echo "  migrate         Run database migrations"
	@echo "  docker-build    Build Docker image"
	@echo "  docker-run      Run Docker container"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt 2>/dev/null || true

test:
	@echo "Running all tests..."
	pytest

test-unit:
	@echo "Running unit tests..."
	pytest -m "unit" -v

test-integration:
	@echo "Running integration tests..."
	pytest -m "integration" -v

test-security:
	@echo "Running security tests..."
	pytest tests/test_auth_security.py -v

test-coverage:
	@echo "Running tests with coverage..."
	pytest --cov=src --cov-report=term-missing --cov-report=html

lint:
	@echo "Running linters..."
	ruff check src tests
	pylint src tests 2>/dev/null || true

format:
	@echo "Formatting code..."
	black src tests
	isort src tests

check-format:
	@echo "Checking code format..."
	black --check src tests
	isort --check-only src tests

type-check:
	@echo "Running type checks..."
	mypy src

security-check:
	@echo "Running security checks..."
	bandit -r src
	safety check

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .mypy_cache
	rm -rf .ruff_cache

run:
	@echo "Starting auth service..."
	uvicorn main_complete:app --host 0.0.0.0 --port 8001

dev:
	@echo "Starting auth service in development mode..."
	uvicorn main_complete:app --host 0.0.0.0 --port 8001 --reload

migrate:
	@echo "Running database migrations..."
	alembic upgrade head

migrate-create:
	@echo "Creating new migration..."
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

docker-build:
	@echo "Building Docker image..."
	docker build -t llmoptimizer-auth-service:latest .

docker-run:
	@echo "Running Docker container..."
	docker run -d \
		--name auth-service \
		-p 8001:8001 \
		--env-file .env \
		--network llmoptimizer-network \
		llmoptimizer-auth-service:latest

# Database commands
db-create:
	@echo "Creating test database..."
	createdb auth_test -U test -h localhost

db-drop:
	@echo "Dropping test database..."
	dropdb auth_test -U test -h localhost --if-exists

db-reset: db-drop db-create migrate
	@echo "Database reset complete"

# Development setup
setup-dev: install db-create migrate
	@echo "Development environment setup complete"

# CI/CD commands
ci-test:
	@echo "Running CI tests..."
	pytest --cov=src --cov-report=xml --junit-xml=test-results.xml

ci-lint:
	@echo "Running CI linting..."
	ruff check src tests --format=github
	black --check src tests

ci-security:
	@echo "Running CI security checks..."
	bandit -r src -f json -o bandit-report.json
	safety check --json > safety-report.json || true