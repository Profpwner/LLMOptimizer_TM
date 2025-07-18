import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, generate_latest
from pythonjsonlogger import jsonlogger
import uvicorn

# Configure logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Database connections
mongo_client: Optional[AsyncIOMotorClient] = None
redis_client: Optional[redis.Redis] = None

# Metrics
login_counter = Counter('auth_login_total', 'Total number of login attempts')
register_counter = Counter('auth_register_total', 'Total number of registrations')
auth_duration = Histogram('auth_request_duration_seconds', 'Auth request duration')

# Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    refresh_token: str

class User(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global mongo_client, redis_client
    
    # MongoDB connection
    mongo_url = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
    mongo_client = AsyncIOMotorClient(mongo_url)
    app.state.db = mongo_client.llmoptimizer
    
    # Redis connection
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = await redis.from_url(redis_url)
    app.state.redis = redis_client
    
    logger.info("Auth service started")
    yield
    
    # Shutdown
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()
    logger.info("Auth service stopped")

# Create FastAPI app
app = FastAPI(
    title="Auth Service",
    description="Authentication and authorization service for LLMOptimizer",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None or payload.get("type") != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await app.state.db.users.find_one({"email": email})
    if user is None:
        raise credentials_exception
    return User(**user)

# Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "1.0.0"
    }

@app.get("/ready")
async def readiness_check():
    try:
        # Check MongoDB
        await app.state.db.command("ping")
        # Check Redis
        await app.state.redis.ping()
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "error": str(e)}
        )

@app.post("/register", response_model=User)
async def register(user_data: UserCreate):
    register_counter.inc()
    
    # Check if user exists
    existing_user = await app.state.db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_dict = {
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "full_name": user_data.full_name,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await app.state.db.users.insert_one(user_dict)
    user_dict["id"] = str(result.inserted_id)
    
    logger.info(f"User registered: {user_data.email}")
    return User(**user_dict)

@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    login_counter.inc()
    
    # Authenticate user
    user = await app.state.db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(data={"sub": user["email"]})
    
    # Store refresh token in Redis
    await app.state.redis.setex(
        f"refresh_token:{user['email']}",
        REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        refresh_token
    )
    
    logger.info(f"User logged in: {form_data.username}")
    return Token(access_token=access_token, refresh_token=refresh_token)

@app.post("/refresh", response_model=Token)
async def refresh_token(token_data: TokenRefresh):
    try:
        payload = jwt.decode(token_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify refresh token in Redis
    stored_token = await app.state.redis.get(f"refresh_token:{email}")
    if not stored_token or stored_token.decode() != token_data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Create new tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email}, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": email})
    
    # Update refresh token in Redis
    await app.state.redis.setex(
        f"refresh_token:{email}",
        REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        new_refresh_token
    )
    
    return Token(access_token=access_token, refresh_token=new_refresh_token)

@app.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    # Remove refresh token from Redis
    await app.state.redis.delete(f"refresh_token:{current_user.email}")
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Successfully logged out"}

@app.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/metrics")
async def metrics():
    return generate_latest()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development"
    )