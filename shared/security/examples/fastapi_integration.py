"""Example FastAPI Integration with Security Framework

This example demonstrates how to integrate the security framework
with a FastAPI application.
"""

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import redis
from typing import Optional, List
from datetime import datetime

# Import security components
from shared.security import (
    JWTHandler,
    RBACManager,
    Permission,
    FieldEncryption,
    SecurityPresets,
    InputValidator,
    RateLimiter,
    RateLimitRule,
    RateLimitStrategy,
    AuditLogger,
    PasswordValidator,
    SessionManager,
    IPManager,
    ThreatDetector,
    SOC2Framework
)

# Initialize Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Initialize security components
jwt_handler = JWTHandler(redis_client)
rbac_manager = RBACManager(redis_client)
field_encryption = FieldEncryption(redis_client)
audit_logger = AuditLogger(redis_client)
password_validator = PasswordValidator(redis_client)
session_manager = SessionManager(redis_client)
ip_manager = IPManager(redis_client, enable_geolocation=True)
threat_detector = ThreatDetector(redis_client, ip_manager)
soc2_framework = SOC2Framework(redis_client, audit_logger)

# Initialize rate limiter with rules
rate_limiter = RateLimiter(redis_client)
rate_limiter.add_rule(RateLimitRule(
    name="login",
    limit=5,
    window=300,  # 5 attempts per 5 minutes
    strategy=RateLimitStrategy.SLIDING_WINDOW
))
rate_limiter.add_rule(RateLimitRule(
    name="api_standard",
    limit=100,
    window=60,  # 100 requests per minute
    strategy=RateLimitStrategy.TOKEN_BUCKET,
    burst_limit=150
))

# Initialize FastAPI app
app = FastAPI(title="LLMOptimizer API", version="1.0.0")

# Apply security middleware
security_middleware = SecurityPresets.api()
app.add_middleware(security_middleware)

# Security scheme
security = HTTPBearer()

# Pydantic models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization: Optional[str] = None

class ContentCreate(BaseModel):
    title: str
    content: str
    tags: List[str] = []
    is_confidential: bool = False

class ContentResponse(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str]
    created_at: datetime
    created_by: str

# Dependencies
async def get_client_ip(request: Request) -> str:
    """Get client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

async def check_rate_limit(request: Request, ip: str = Depends(get_client_ip)):
    """Rate limiting dependency"""
    # Determine rule based on endpoint
    if request.url.path == "/auth/login":
        rule_name = "login"
    else:
        rule_name = "api_standard"
    
    result = rate_limiter.check_rate_limit(ip, rule_name)
    
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": str(result.retry_after)}
        )
    
    # Add rate limit headers to response
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(result.reset)
    }

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Verify JWT token and return user info"""
    token = credentials.credentials
    payload = jwt_handler.verify_access_token(token)
    
    if not payload:
        # Log failed authentication
        audit_logger.log_authentication(
            success=False,
            error_message="Invalid token"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return payload

def require_permission(permission: Permission):
    """Permission checking dependency"""
    async def check_permission(
        user=Depends(get_current_user),
        request: Request = None
    ):
        user_id = user["sub"]
        
        # Check permission
        if not rbac_manager.has_permission(user_id, permission):
            # Log authorization failure
            audit_logger.log_event(
                event_type="auth.permission.denied",
                user_id=user_id,
                metadata={
                    "permission": permission.value,
                    "endpoint": request.url.path if request else None
                }
            )
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        
        return user
    
    return check_permission

# Middleware for adding rate limit headers
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add rate limit headers if available
    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value
    
    return response

# Middleware for audit logging
@app.middleware("http")
async def audit_logging_middleware(request: Request, call_next):
    # Generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        import uuid
        correlation_id = str(uuid.uuid4())
    
    audit_logger.set_correlation_id(correlation_id)
    
    # Track request timing
    start_time = datetime.utcnow()
    
    # Process request
    response = await call_next(request)
    
    # Calculate response time
    response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    # Log API call
    user_id = None
    if hasattr(request.state, "user"):
        user_id = request.state.user.get("sub")
    
    audit_logger.log_api_call(
        method=request.method,
        path=request.url.path,
        user_id=user_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
        status_code=response.status_code,
        response_time=response_time
    )
    
    # Add correlation ID to response
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response

# Authentication endpoints
@app.post("/auth/login", response_model=LoginResponse, dependencies=[Depends(check_rate_limit)])
async def login(
    login_data: LoginRequest,
    request: Request,
    ip: str = Depends(get_client_ip)
):
    """User login endpoint"""
    # Input validation
    validator = InputValidator()
    email = validator.validate_email(login_data.email)
    
    # Check for threats
    threats = threat_detector.check_threats(ip, login_data.email)
    if threats:
        # Log security event
        for threat in threats:
            if threat["severity"] in ["high", "critical"]:
                audit_logger.log_security_event(
                    threat_type=threat["type"],
                    severity=threat["severity"],
                    source_ip=ip,
                    description=threat["description"]
                )
        
        if any(t["severity"] == "critical" for t in threats):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Authenticate user (placeholder - implement actual authentication)
    # In production, verify password against stored hash
    user_id = "user123"  # Retrieved from database
    
    # Track failed login if authentication fails
    if not user_id:  # Authentication failed
        threat_detector.track_event("failed_login", ip, email)
        audit_logger.log_authentication(
            success=False,
            user_email=email,
            ip_address=ip,
            error_message="Invalid credentials"
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_id = session_manager.create_session(
        user_id=user_id,
        ip_address=ip,
        user_agent=request.headers.get("User-Agent"),
        device_id=login_data.device_id
    )
    
    # Generate tokens
    access_token, refresh_token, token_info = jwt_handler.generate_tokens(
        user_id=user_id,
        claims={
            "email": email,
            "session_id": session_id
        },
        device_id=login_data.device_id
    )
    
    # Log successful authentication
    audit_logger.log_authentication(
        success=True,
        user_id=user_id,
        user_email=email,
        ip_address=ip,
        metadata={"session_id": session_id}
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=token_info["expires_in"]
    )

@app.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    """User logout endpoint"""
    user_id = user["sub"]
    session_id = user.get("session_id")
    
    # Destroy session
    if session_id:
        session_manager.destroy_session(session_id)
    
    # Revoke tokens
    jwt_handler.revoke_tokens(user_id, user.get("device_id"))
    
    # Log logout
    audit_logger.log_event(
        event_type="auth.logout",
        user_id=user_id
    )
    
    return {"message": "Logged out successfully"}

@app.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    result = jwt_handler.refresh_access_token(refresh_token)
    
    if not result:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    access_token, new_refresh_token, token_info = result
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": token_info["expires_in"]
    }

# User management endpoints
@app.post("/users", dependencies=[Depends(require_permission(Permission.USER_CREATE))])
async def create_user(
    user_data: UserCreate,
    current_user=Depends(get_current_user)
):
    """Create new user"""
    # Validate password
    is_valid, errors = password_validator.validate_password(
        user_data.password,
        user_info={
            "email": user_data.email,
            "name": user_data.full_name
        }
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    # Hash password
    password_hash = password_validator.hash_password(user_data.password)
    
    # Create user (placeholder - implement actual user creation)
    user_id = "new_user_id"
    
    # Assign default role
    rbac_manager.assign_role(user_id, "viewer")
    
    # Log user creation
    audit_logger.log_event(
        event_type="user.create",
        user_id=current_user["sub"],
        resource_id=user_id,
        metadata={
            "email": user_data.email,
            "organization": user_data.organization
        }
    )
    
    return {"user_id": user_id, "email": user_data.email}

# Content management endpoints
@app.post("/content", response_model=ContentResponse)
async def create_content(
    content_data: ContentCreate,
    current_user=Depends(require_permission(Permission.CONTENT_CREATE))
):
    """Create new content"""
    # Input validation
    validator = InputValidator()
    
    # Validate and sanitize title
    title = validator.validate_string(
        content_data.title,
        min_length=3,
        max_length=200,
        pattern="safe_string"
    )
    
    # Validate content (allow HTML if needed)
    content = validator.validate_string(
        content_data.content,
        max_length=50000,
        allow_html=True,
        strip_html=False
    )
    
    # Encrypt confidential content
    if content_data.is_confidential:
        encrypted_content = field_encryption.encrypt_field(
            content,
            field_name="content",
            context={"user_id": current_user["sub"]}
        )
        content_to_store = encrypted_content
    else:
        content_to_store = content
    
    # Create content (placeholder - implement actual content creation)
    content_id = "content_123"
    created_at = datetime.utcnow()
    
    # Log data access
    audit_logger.log_data_access(
        action="write",
        resource_type="content",
        resource_id=content_id,
        user_id=current_user["sub"],
        metadata={
            "title": title,
            "is_confidential": content_data.is_confidential
        }
    )
    
    return ContentResponse(
        id=content_id,
        title=title,
        content=content if not content_data.is_confidential else "[ENCRYPTED]",
        tags=content_data.tags,
        created_at=created_at,
        created_by=current_user["sub"]
    )

@app.get("/content/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: str,
    current_user=Depends(require_permission(Permission.CONTENT_READ))
):
    """Get content by ID"""
    # Retrieve content (placeholder)
    content_data = {
        "id": content_id,
        "title": "Sample Content",
        "content": {"ciphertext": "..."},  # Encrypted content
        "is_encrypted": True,
        "tags": ["sample"],
        "created_at": datetime.utcnow(),
        "created_by": "user123"
    }
    
    # Decrypt if encrypted
    if content_data.get("is_encrypted"):
        decrypted_content = field_encryption.decrypt_field(
            content_data["content"],
            expected_field_name="content"
        )
        content_data["content"] = decrypted_content
    
    # Log data access
    audit_logger.log_data_access(
        action="read",
        resource_type="content",
        resource_id=content_id,
        user_id=current_user["sub"]
    )
    
    return ContentResponse(**content_data)

# Health check endpoint (no auth required)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# Compliance endpoints
@app.get("/compliance/report", dependencies=[Depends(require_permission(Permission.SYSTEM_AUDIT))])
async def get_compliance_report(
    start_date: datetime,
    end_date: datetime,
    current_user=Depends(get_current_user)
):
    """Generate SOC2 compliance report"""
    report = soc2_framework.generate_compliance_report(
        start_date=start_date,
        end_date=end_date
    )
    
    # Log report generation
    audit_logger.log_event(
        event_type="compliance.report.generated",
        user_id=current_user["sub"],
        metadata={
            "report_id": report["report_id"],
            "period": f"{start_date} to {end_date}"
        }
    )
    
    return report

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with security considerations"""
    # Log security-relevant errors
    if exc.status_code in [401, 403]:
        audit_logger.log_event(
            event_type="security.access.denied",
            severity="warning",
            metadata={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
                "ip_address": request.client.host
            }
        )
    
    # Don't expose internal details in production
    if exc.status_code >= 500:
        return {"detail": "Internal server error"}
    
    return {"detail": exc.detail}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize security components on startup"""
    # Log system start
    audit_logger.log_event(
        event_type="system.start",
        metadata={"version": "1.0.0"}
    )
    
    # Start SOC2 automated checks
    # await soc2_framework.start_automated_checks()
    
    print("Security framework initialized")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    # Log system stop
    audit_logger.log_event(
        event_type="system.stop"
    )
    
    # Close connections
    audit_logger.close()
    
    print("Security framework shutdown complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)