# LLMOptimizer Development Environment

This directory contains all documentation and guides for developing the LLMOptimizer platform.

## Quick Start

To set up your development environment, run these commands in order:

```bash
# 1. Install development tools
./scripts/dev/install-dev-tools.sh

# 2. Set up local Kubernetes cluster (Minikube or Kind)
./scripts/dev/setup-local-k8s.sh         # Uses Minikube by default
# OR
./scripts/dev/setup-local-k8s.sh kind    # Use Kind instead

# 3. Initialize the complete development environment
./scripts/dev/init-dev-env.sh
```

## Available Scripts

### Core Setup Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `install-dev-tools.sh` | Installs all required development tools | `./scripts/dev/install-dev-tools.sh` |
| `setup-local-k8s.sh` | Configures local Kubernetes cluster | `./scripts/dev/setup-local-k8s.sh [minikube|kind]` |
| `init-dev-env.sh` | Initializes complete dev environment | `./scripts/dev/init-dev-env.sh` |

### Utility Scripts

After running `init-dev-env.sh`, these utilities are available:

| Script | Purpose | Usage |
|--------|---------|-------|
| `check-health.sh` | Check health of all services | `./scripts/dev/utils/check-health.sh` |
| `view-logs.sh` | View logs from services | `./scripts/dev/utils/view-logs.sh [namespace] [service]` |
| `port-forward.sh` | Set up port forwarding for databases | `./scripts/dev/utils/port-forward.sh` |
| `backup-db.sh` | Backup development databases | `./scripts/dev/utils/backup-db.sh` |

## Makefile Commands

A comprehensive Makefile is provided for common tasks:

```bash
make help           # Show all available commands
make build          # Build all Docker images
make deploy         # Deploy to local Kubernetes
make test           # Run all tests
make logs           # View logs from all services
make health         # Check service health
make port-forward   # Set up database port forwarding
make clean          # Clean up all resources
make reset          # Reset entire environment
```

## Development Tools Installed

The `install-dev-tools.sh` script installs:

### Container & Orchestration
- Docker & Docker Compose
- Kubernetes CLI (kubectl)
- Minikube (local K8s)
- Kind (alternative local K8s)
- Helm (package manager)
- Skaffold (continuous deployment)

### Kubernetes Tools
- k9s (terminal UI)
- stern (multi-pod log tailing)
- kubectx/kubens (context switching)

### Language-Specific
- Python 3.11+ with pip, black, flake8, mypy, pytest
- Go 1.21+ with golangci-lint, goimports, delve
- Node.js & npm (for frontend development)

### Database Clients
- PostgreSQL client (psql)
- Redis client (redis-cli)
- MongoDB client (mongosh)

### Development Utilities
- jq (JSON processing)
- yq (YAML processing)
- httpie (HTTP client)
- git-flow
- tmux
- htop/ctop
- lazydocker

## VS Code Setup

The environment includes VS Code configuration:

### Settings
- Python linting with flake8 and mypy
- Go formatting with goimports
- Auto-format on save
- Kubernetes and Docker integration

### Debug Configurations
Pre-configured debugging for:
- Auth Service (Python)
- Billing Service (Python)
- Notification Service (Python)
- API Gateway (Go)
- Analytics Service (Go)
- Remote debugging for K8s pods

### Recommended Extensions
Run VS Code and install recommended extensions when prompted, including:
- Python & Pylance
- Go
- Kubernetes Tools
- Docker
- GitLens
- REST Client

## Local Services

After setup, these services are available:

### Application Services
- **API Gateway**: `http://api.llmoptimizer.local`
- **Auth Service**: `http://auth.llmoptimizer.local`
- **Billing Service**: `http://billing.llmoptimizer.local`
- **Notification Service**: `http://notifications.llmoptimizer.local`
- **Analytics Service**: `http://analytics.llmoptimizer.local`

### Infrastructure Services
- **PostgreSQL**: `localhost:5432` (user: postgres, pass: postgres123)
- **Redis**: `localhost:6379` (pass: redis123)
- **RabbitMQ**: `localhost:15672` (user: admin, pass: admin123)
- **MongoDB**: `localhost:27017` (user: admin, pass: admin123)
- **Docker Registry**: `localhost:5000`

### Monitoring
- **Kubernetes Dashboard**: Run `minikube dashboard -p llmoptimizer-dev`
- **Grafana**: `http://monitoring.llmoptimizer.local` (coming soon)
- **Prometheus**: `http://monitoring.llmoptimizer.local:9090` (coming soon)

## Environment Variables

Development environment variables are stored in `.env.local` (created by `init-dev-env.sh`).

**Important**: Never commit `.env.local` to version control!

## API Testing

### Postman Collection
Import the collection from `tests/api/llmoptimizer.postman_collection.json`

### HTTPie Examples
Run API tests using HTTPie:
```bash
./tests/api/httpie-examples.sh
```

### Manual Testing
```bash
# Health check
curl http://api.llmoptimizer.local/health

# With httpie
http GET api.llmoptimizer.local/health
```

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for solutions to common issues.

### Quick Fixes

**Reset everything:**
```bash
make reset
```

**Clean Docker:**
```bash
docker system prune -a --volumes
```

**Restart Kubernetes:**
```bash
minikube stop -p llmoptimizer-dev
minikube start -p llmoptimizer-dev
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed system architecture.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests: `make test`
4. Submit a pull request

## Support

- Slack: #llmoptimizer-dev
- Email: dev-team@llmoptimizer.com
- Wiki: https://wiki.llmoptimizer.internal