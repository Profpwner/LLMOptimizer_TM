# LLM Optimizer - Complete Setup Guide

## Overview

LLM Optimizer is an enterprise-grade platform for optimizing content visibility across AI language models (ChatGPT, Claude, Perplexity, Gemini). The application includes multi-tenant support, usage-based billing, real-time optimization, and comprehensive analytics.

## Current Status

### ✅ Completed
- Frontend layout and routing structure
- Basic authentication flow (needs real JWT implementation)
- Dashboard UI with charts
- Redux state management setup
- Multi-tenant database schema

### 🔧 Needs Implementation
1. **Backend Services**
   - Real authentication with JWT tokens
   - Database connections and migrations
   - LLM API integrations
   - Content optimization engine
   - WebSocket real-time updates
   - Billing integration with Stripe

2. **Frontend Integration**
   - Connect to real backend APIs
   - Implement actual data fetching
   - Real-time updates via WebSocket
   - Error handling and loading states

## Required API Keys

To run the full application, you'll need the following API keys:

### 1. LLM APIs
- **OpenAI API Key**: For GPT models - [Get it here](https://platform.openai.com/api-keys)
- **Anthropic API Key**: For Claude - [Get it here](https://console.anthropic.com/)
- **Google AI API Key**: For Gemini - [Get it here](https://makersuite.google.com/app/apikey)
- **Perplexity API Key**: For Perplexity - [Get it here](https://www.perplexity.ai/api)

### 2. Stripe (for billing)
- **Stripe Secret Key**: [Get it here](https://dashboard.stripe.com/apikeys)
- **Stripe Publishable Key**: From the same page
- **Stripe Webhook Secret**: After setting up webhooks

### 3. Email (for notifications)
- SMTP credentials (Gmail, SendGrid, etc.)

## Quick Start

### 1. Clone and Install
```bash
# Clone the repository
git clone <repository-url>
cd LLMOptimizer_CC

# Install backend dependencies
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install
```

### 2. Set Up Environment Variables
```bash
# In backend directory
cp .env.example .env
# Edit .env with your API keys
```

### 3. Start Services
```bash
# Start Docker services (PostgreSQL, Redis, etc.)
docker-compose up -d

# Run database migrations
cd backend
alembic upgrade head

# Start backend
python -m uvicorn app.main:app --reload

# In another terminal, start frontend
cd frontend
npm start
```

## Architecture

### Backend Stack
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis
- **Queue**: RabbitMQ with Celery
- **Search**: Elasticsearch
- **Graph DB**: Neo4j (for knowledge graphs)
- **Vector DB**: Weaviate (for semantic search)

### Frontend Stack
- **Framework**: React with TypeScript
- **State**: Redux Toolkit
- **UI**: Material-UI
- **Charts**: Chart.js
- **3D**: Three.js (for knowledge graph visualization)
- **Build**: Vite

### Key Features
1. **Multi-Tenant Architecture**: Complete isolation between customers
2. **Usage-Based Billing**: Stripe integration with metered billing
3. **Real-Time Updates**: WebSocket connections for live data
4. **LLM Optimization**: Content scoring across multiple AI platforms
5. **Analytics Dashboard**: Comprehensive metrics and insights

## Development Workflow

### Backend Development
```bash
cd backend
source venv/bin/activate

# Run tests
pytest

# Format code
black .

# Lint
pylint app/

# Type checking
mypy app/
```

### Frontend Development
```bash
cd frontend

# Run tests
npm test

# Lint
npm run lint

# Type checking
npm run type-check

# Build
npm run build
```

## Production Deployment

### 1. Environment Setup
- Set all environment variables for production
- Use strong SECRET_KEY
- Configure proper database credentials
- Set up SSL certificates

### 2. Database
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
- Set up regular backups
- Configure read replicas for scaling

### 3. Caching & Queuing
- Use managed Redis (AWS ElastiCache, etc.)
- Configure RabbitMQ cluster for reliability

### 4. Application Deployment
- Use Docker containers
- Deploy with Kubernetes or ECS
- Set up auto-scaling
- Configure load balancers

### 5. Monitoring
- Set up Sentry for error tracking
- Configure Prometheus + Grafana for metrics
- Set up alerts for critical issues

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Support

For issues and questions:
- Create an issue in the repository
- Check the documentation in `/docs`
- Review the architecture diagrams

## Next Steps for Full Implementation

1. **Complete Backend Services**
   - Implement all service modules in `/backend/app/services/`
   - Add proper error handling and logging
   - Implement rate limiting and security

2. **LLM Integrations**
   - Create unified interface for all LLM providers
   - Implement retry logic and fallbacks
   - Add response caching

3. **Testing**
   - Add comprehensive unit tests
   - Create integration tests
   - Set up end-to-end tests

4. **Documentation**
   - Complete API documentation
   - Add code comments
   - Create user guides

## License

[Your License Here]