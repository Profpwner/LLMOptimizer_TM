# LLM Optimizer Deployment Guide

## Table of Contents
1. [Development Environment](#development-environment)
2. [Production Deployment](#production-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Monitoring & Logging](#monitoring--logging)
6. [Troubleshooting](#troubleshooting)

## Development Environment

### Prerequisites
- Python 3.10.11 or higher
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for frontend)

### Quick Start

1. **Clone the repository:**
```bash
git clone <repository-url>
cd LLMOptimizer_CC
```

2. **Set up environment:**
```bash
make setup  # Installs all dependencies and initializes databases
```

3. **Start development servers:**
```bash
make dev  # Starts all services in development mode
```

### Manual Setup

If you prefer manual setup:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Frontend
cd ../frontend
npm install
```

### Running the Backend Server

Use the production-ready startup script:

```bash
cd backend
./start_server.sh
```

Or manually:

```bash
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Production Deployment

### System Requirements

- Ubuntu 20.04+ or RHEL 8+
- 4+ CPU cores
- 16GB+ RAM
- 100GB+ SSD storage
- Docker 20.10+ and Docker Compose 2.0+

### Security Considerations

1. **Environment Variables:**
   - Never commit `.env` files
   - Use strong, randomly generated secrets
   - Rotate keys regularly

2. **Network Security:**
   - Use HTTPS/TLS for all connections
   - Implement rate limiting
   - Use firewalls to restrict access

3. **Database Security:**
   - Use strong passwords
   - Enable SSL/TLS for database connections
   - Regular backups

### Deployment Steps

1. **Prepare the server:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. **Configure environment:**
```bash
cp .env.production.example .env.production
# Edit .env.production with your values
vim .env.production
```

3. **Deploy with Docker Compose:**
```bash
docker-compose -f docker-compose.production.yml up -d
```

4. **Run database migrations:**
```bash
docker-compose -f docker-compose.production.yml exec backend alembic upgrade head
```

5. **Create initial admin user:**
```bash
docker-compose -f docker-compose.production.yml exec backend python -m app.cli create-admin
```

## Docker Deployment

### Building Images

```bash
# Build all images
docker-compose -f docker-compose.production.yml build

# Build specific service
docker-compose -f docker-compose.production.yml build backend
```

### Managing Services

```bash
# Start all services
docker-compose -f docker-compose.production.yml up -d

# View logs
docker-compose -f docker-compose.production.yml logs -f backend

# Stop services
docker-compose -f docker-compose.production.yml down

# Remove volumes (WARNING: deletes data)
docker-compose -f docker-compose.production.yml down -v
```

### Scaling

```bash
# Scale backend workers
docker-compose -f docker-compose.production.yml up -d --scale backend=4
```

## Kubernetes Deployment

### Prerequisites
- Kubernetes 1.25+
- Helm 3+
- kubectl configured

### Deploy with Helm

```bash
# Add Helm repository
helm repo add llm-optimizer https://charts.llmoptimizer.com
helm repo update

# Install
helm install llm-optimizer llm-optimizer/llm-optimizer \
  --namespace llm-optimizer \
  --create-namespace \
  --values values.production.yaml
```

### Manual Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace llm-optimizer

# Create secrets
kubectl create secret generic llm-optimizer-secrets \
  --from-env-file=.env.production \
  -n llm-optimizer

# Apply manifests
kubectl apply -f deploy/kubernetes/ -n llm-optimizer
```

## Monitoring & Logging

### Prometheus Metrics

The application exposes metrics at `/metrics` endpoint:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'llm-optimizer'
    static_configs:
      - targets: ['backend:8000']
```

### Grafana Dashboards

Import the provided dashboards from `deploy/grafana/`:
- API Performance Dashboard
- Business Metrics Dashboard
- System Health Dashboard

### Log Aggregation

Configure log shipping to your preferred solution:

```yaml
# For ELK Stack
logging:
  driver: "syslog"
  options:
    syslog-address: "tcp://logstash:5000"
    tag: "llm-optimizer-{{.Name}}"
```

### Health Checks

- Backend health: `GET /health`
- Database health: `GET /health/db`
- Full status: `GET /health/full`

## Troubleshooting

### Common Issues

1. **Import Errors (ModuleNotFoundError)**
   - Ensure virtual environment is activated
   - Run `pip install -r requirements.txt`
   - Check Python version compatibility

2. **Database Connection Errors**
   - Verify database services are running
   - Check connection strings in `.env`
   - Ensure network connectivity

3. **Permission Errors**
   - Check file permissions
   - Ensure proper user/group ownership
   - Verify Docker socket permissions

### Debugging

1. **Enable debug logging:**
```bash
export LOG_LEVEL=DEBUG
./start_server.sh
```

2. **Check service status:**
```bash
# Docker
docker-compose -f docker-compose.production.yml ps

# Systemd
systemctl status llm-optimizer
```

3. **View detailed logs:**
```bash
# Docker logs
docker-compose -f docker-compose.production.yml logs -f --tail=100 backend

# System logs
journalctl -u llm-optimizer -f
```

### Performance Tuning

1. **Database optimization:**
   - Adjust connection pool sizes
   - Enable query caching
   - Add appropriate indexes

2. **Application tuning:**
   - Increase worker processes
   - Adjust memory limits
   - Enable response caching

3. **Infrastructure scaling:**
   - Use load balancers
   - Implement horizontal scaling
   - Use CDN for static assets

## Support

For issues and questions:
1. Check the documentation
2. Search existing issues on GitHub
3. Create a new issue with detailed information
4. Contact support (for enterprise customers)