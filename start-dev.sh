#!/bin/bash

echo "🚀 Starting LLMOptimizer Development Environment"
echo "=============================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your API keys."
fi

# Start databases first
echo ""
echo "📦 Starting databases..."
docker-compose -f docker-compose.dev.yml up -d mongodb redis postgres

# Wait for databases to be ready
echo "⏳ Waiting for databases to start..."
sleep 10

# Start auth service
echo ""
echo "🔐 Starting auth service..."
cd auth-service
python -m venv venv 2>/dev/null || true
source venv/bin/activate || source venv/Scripts/activate
pip install -r requirements.txt --quiet
python main_complete.py &
AUTH_PID=$!
cd ..

# Start frontend
echo ""
echo "🎨 Starting frontend applications..."
echo "Main Dashboard will be available at: http://localhost:3000"

cd frontend/dashboard
npm install --silent
npm start &
FRONTEND_PID=$!
cd ../..

echo ""
echo "=============================================="
echo "✅ Development environment is starting!"
echo ""
echo "Available services:"
echo "  - Auth Service: http://localhost:8001"
echo "  - Main Dashboard: http://localhost:3000"
echo "  - MongoDB: localhost:27017"
echo "  - Redis: localhost:6379"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=============================================="

# Wait for interrupt
trap "echo 'Shutting down...'; kill $AUTH_PID $FRONTEND_PID; docker-compose -f docker-compose.dev.yml down; exit" INT
wait