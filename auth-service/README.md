# Auth Service

The Authentication Service handles user registration, login, and token management for the LLMOptimizer platform.

## Features

- User registration and login
- JWT-based authentication
- Access and refresh tokens
- Password hashing with bcrypt
- Token storage in Redis
- User data storage in MongoDB
- Prometheus metrics
- Structured JSON logging

## Technology Stack

- **Language**: Python 3.11
- **Framework**: FastAPI
- **Database**: MongoDB (user storage)
- **Cache**: Redis (token storage)
- **Authentication**: JWT (JSON Web Tokens)
- **Password Hashing**: bcrypt

## API Endpoints

### Public Endpoints
- `POST /register` - Register new user
- `POST /login` - User login (returns access and refresh tokens)
- `POST /refresh` - Refresh access token
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics

### Protected Endpoints
- `GET /me` - Get current user info
- `POST /logout` - Logout user

## Request/Response Examples

### Register
```json
POST /register
{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

### Login
```json
POST /login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword123
```

### Response
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `8000` |
| `SECRET_KEY` | JWT secret key | `your-secret-key-here` |
| `MONGODB_URL` | MongoDB connection string | `mongodb://mongodb:27017` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiration | `7` |

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

## Security Considerations

- Passwords are hashed using bcrypt
- JWT tokens have expiration times
- Refresh tokens are stored in Redis with TTL
- All endpoints use HTTPS in production
- Rate limiting should be implemented at API Gateway level

## Monitoring

- Health endpoint: `http://localhost:8000/health`
- Metrics endpoint: `http://localhost:8000/metrics`
- Structured JSON logs for easy parsing