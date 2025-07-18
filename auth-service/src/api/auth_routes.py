"""Comprehensive authentication API routes."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..database import get_db, get_redis
from ..config import settings
from ..models.user import User, UserStatus
from ..models.session import UserSession, SessionStatus
from ..models.rbac import Role
from ..security.tokens import TokenService, TokenType
from ..security.passwords import PasswordService
from ..security.rate_limiter import RateLimiter
from ..security.device import DeviceFingerprint
from ..oauth.manager import OAuthManager
from ..saml.saml_manager import SAMLManager
from ..mfa.manager import MFAManager
from .schemas import (
    UserCreate, UserLogin, Token, TokenRefresh,
    MFASetupRequest, MFAVerifyRequest, OAuthCallback,
    SAMLCallback, UserResponse, SessionResponse
)
from .dependencies import (
    get_current_user, require_mfa, require_admin,
    get_session_info, verify_csrf_token
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize services
token_service = TokenService()
password_service = PasswordService()
device_fingerprint = DeviceFingerprint()
rate_limiter = RateLimiter()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Register a new user."""
    # Rate limiting
    await rate_limiter.check_rate_limit(
        redis_client,
        f"register:{request.client.host}",
        max_attempts=5,
        window=3600
    )
    
    # Check if user exists
    existing_user = await db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Validate password strength
    if not password_service.validate_password_strength(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet security requirements"
        )
    
    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        password_hash=password_service.hash_password(user_data.password),
        status=UserStatus.PENDING_VERIFICATION,
        is_email_verified=False,
        timezone=user_data.timezone or "UTC",
        locale=user_data.locale or "en"
    )
    
    db.add(user)
    
    # Assign default role
    default_role = await db.query(Role).filter(Role.name == "user").first()
    if default_role:
        user.roles.append(default_role)
    
    await db.commit()
    await db.refresh(user)
    
    # Send verification email
    verification_token = token_service.create_email_verification_token(
        email=user.email,
        user_id=str(user.id)
    )
    
    # TODO: Send email with verification_token
    
    return UserResponse.from_orm(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    response: Response = None,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Login with username/password."""
    # Rate limiting
    await rate_limiter.check_rate_limit(
        redis_client,
        f"login:{request.client.host}",
        max_attempts=10,
        window=900
    )
    
    # Find user
    user = await db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Check password
    if not password_service.verify_password(form_data.password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.status = UserStatus.LOCKED
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            user.lock_reason = "Too many failed login attempts"
        
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Check if user can login
    if not user.can_login():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active or verified"
        )
    
    # Reset failed attempts
    user.failed_login_attempts = 0
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host
    
    # Get device info
    device_info = device_fingerprint.extract_device_info(request)
    fingerprint = device_fingerprint.generate_fingerprint(device_info)
    
    # Check if MFA is required
    if user.mfa_enabled:
        # Create temporary MFA token
        mfa_token = token_service.create_mfa_token(
            user_id=str(user.id),
            method="pending"
        )
        
        return Token(
            access_token=mfa_token,
            token_type="mfa_required",
            mfa_required=True,
            mfa_methods=user.mfa_methods
        )
    
    # Create session
    session = UserSession(
        user_id=user.id,
        session_token=token_service.generate_api_key()[0],
        refresh_token=token_service.generate_api_key()[0],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=fingerprint,
        device_type=device_info.get("device_type"),
        browser=device_info.get("browser"),
        os=device_info.get("os"),
        expires_at=datetime.utcnow() + timedelta(days=30),
        login_method="password",
        mfa_verified=False
    )
    
    db.add(session)
    await db.commit()
    
    # Create tokens
    access_token = token_service.create_access_token(
        user_id=str(user.id),
        session_id=str(session.id),
        device_fingerprint=fingerprint
    )
    
    refresh_token = token_service.create_refresh_token(
        user_id=str(user.id),
        session_id=str(session.id),
        device_fingerprint=fingerprint
    )
    
    # Set secure cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60  # 30 days
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Refresh access token."""
    try:
        # Verify refresh token
        token_payload = token_service.verify_token(
            token_data.refresh_token,
            TokenType.REFRESH
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    
    # Get session
    session = await db.query(UserSession).filter(
        UserSession.id == token_payload.session_id,
        UserSession.user_id == token_payload.sub
    ).first()
    
    if not session or not session.is_active():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    # Update session activity
    session.last_activity = datetime.utcnow()
    
    # Create new tokens
    access_token = token_service.create_access_token(
        user_id=str(session.user_id),
        session_id=str(session.id),
        device_fingerprint=session.device_fingerprint
    )
    
    # Optionally rotate refresh token
    if session.should_refresh():
        new_refresh_token = token_service.create_refresh_token(
            user_id=str(session.user_id),
            session_id=str(session.id),
            device_fingerprint=session.device_fingerprint
        )
        session.refresh_token = new_refresh_token
    else:
        new_refresh_token = token_data.refresh_token
    
    await db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    session: UserSession = Depends(get_session_info),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Logout current session."""
    # Revoke session
    session.status = SessionStatus.REVOKED
    session.revoked_at = datetime.utcnow()
    session.revoke_reason = "User logout"
    
    # Blacklist tokens
    await redis_client.setex(
        f"blacklist:access:{session.session_token}",
        settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "1"
    )
    
    await redis_client.setex(
        f"blacklist:refresh:{session.refresh_token}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "1"
    )
    
    await db.commit()
    
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Logout all user sessions."""
    # Revoke all active sessions
    sessions = await db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.status == SessionStatus.ACTIVE
    ).all()
    
    for session in sessions:
        session.status = SessionStatus.REVOKED
        session.revoked_at = datetime.utcnow()
        session.revoke_reason = "User logout all"
        
        # Blacklist tokens
        await redis_client.setex(
            f"blacklist:access:{session.session_token}",
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "1"
        )
        
        await redis_client.setex(
            f"blacklist:refresh:{session.refresh_token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            "1"
        )
    
    await db.commit()
    
    return {"message": "Successfully logged out from all sessions"}


# OAuth Routes
@router.get("/oauth/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Initiate OAuth login."""
    oauth_manager = OAuthManager(redis_client)
    
    try:
        auth_url, state = await oauth_manager.create_authorization_url(
            provider,
            user_ip=request.client.host,
            user_agent=request.headers.get("user-agent", "")
        )
        
        return {"auth_url": auth_url, "state": state}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/oauth/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Handle OAuth callback."""
    oauth_manager = OAuthManager(redis_client)
    
    try:
        # Validate callback
        result = await oauth_manager.validate_callback(
            provider,
            state,
            code,
            request.client.host
        )
        
        # Find or create user
        user_info = result["user_info"]
        email = user_info.get("email")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by OAuth provider"
            )
        
        user = await db.query(User).filter(User.email == email).first()
        
        if not user:
            # Create new user from OAuth
            user = User(
                email=email,
                username=user_info.get("username", email.split("@")[0]),
                full_name=user_info.get("name", ""),
                is_email_verified=True,  # Trust OAuth provider
                status=UserStatus.ACTIVE,
                metadata={
                    "source": "oauth",
                    "provider": provider
                }
            )
            db.add(user)
            await db.commit()
        
        # Create session and tokens
        session = UserSession(
            user_id=user.id,
            session_token=token_service.generate_api_key()[0],
            refresh_token=token_service.generate_api_key()[0],
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(days=30),
            login_method="oauth",
            oauth_provider=provider
        )
        
        db.add(session)
        await db.commit()
        
        # Create tokens
        access_token = token_service.create_access_token(
            user_id=str(user.id),
            session_id=str(session.id)
        )
        
        refresh_token = token_service.create_refresh_token(
            user_id=str(user.id),
            session_id=str(session.id)
        )
        
        # Redirect to frontend with tokens
        redirect_url = f"{settings.FRONTEND_URL}/auth/callback"
        redirect_url += f"?access_token={access_token}&refresh_token={refresh_token}"
        
        return RedirectResponse(url=redirect_url)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# SAML Routes
@router.get("/saml/{provider}")
async def saml_login(
    provider: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Initiate SAML SSO."""
    saml_manager = SAMLManager(db, redis_client)
    
    try:
        sso_request = await saml_manager.create_sso_request(provider)
        
        if sso_request["method"] == "GET":
            return RedirectResponse(url=sso_request["url"])
        else:
            # Return form for POST binding
            return {
                "method": "POST",
                "url": sso_request["url"],
                "saml_request": sso_request["saml_request"],
                "relay_state": sso_request["relay_state"]
            }
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/saml/callback/{provider}")
async def saml_callback(
    provider: str,
    SAMLResponse: str = Form(...),
    RelayState: str = Form(...),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Handle SAML SSO callback."""
    saml_manager = SAMLManager(db, redis_client)
    
    try:
        # Process SAML response
        result = await saml_manager.process_sso_response(
            provider,
            SAMLResponse,
            RelayState
        )
        
        user = result["user"]
        
        # Create session
        session = UserSession(
            user_id=user.id,
            session_token=token_service.generate_api_key()[0],
            refresh_token=token_service.generate_api_key()[0],
            expires_at=datetime.utcnow() + timedelta(days=30),
            login_method="saml",
            oauth_provider=f"saml_{provider}",
            metadata={
                "session_index": result.get("session_index")
            }
        )
        
        db.add(session)
        await db.commit()
        
        # Redirect to frontend with tokens
        redirect_url = f"{settings.FRONTEND_URL}/auth/callback"
        redirect_url += f"?access_token={result['access_token']}"
        redirect_url += f"&refresh_token={result['refresh_token']}"
        
        if result.get("relay_state"):
            redirect_url += f"&relay_state={result['relay_state']}"
        
        return RedirectResponse(url=redirect_url)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# MFA Routes
@router.post("/mfa/setup/{method}")
async def setup_mfa(
    method: str,
    setup_data: MFASetupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Setup MFA method."""
    mfa_manager = MFAManager(db, redis_client)
    
    try:
        result = await mfa_manager.setup_mfa(
            user_id=str(current_user.id),
            method=method,
            **setup_data.dict()
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/mfa/verify")
async def verify_mfa(
    verify_data: MFAVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Verify MFA code after login."""
    # Verify MFA token
    try:
        mfa_token_data = token_service.verify_token(
            verify_data.mfa_token,
            TokenType.MFA
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA token"
        )
    
    user_id = mfa_token_data.sub
    
    # Verify MFA code
    mfa_manager = MFAManager(db, redis_client)
    result = await mfa_manager.verify_mfa(
        user_id=user_id,
        method=verify_data.method,
        code=verify_data.code
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.get("error", "Invalid MFA code")
        )
    
    # Get user
    user = await db.query(User).filter(User.id == user_id).first()
    
    # Create authenticated session
    device_info = device_fingerprint.extract_device_info(request)
    fingerprint = device_fingerprint.generate_fingerprint(device_info)
    
    session = UserSession(
        user_id=user_id,
        session_token=token_service.generate_api_key()[0],
        refresh_token=token_service.generate_api_key()[0],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=fingerprint,
        expires_at=datetime.utcnow() + timedelta(days=30),
        login_method="password",
        mfa_verified=True
    )
    
    db.add(session)
    await db.commit()
    
    # Create tokens
    access_token = token_service.create_access_token(
        user_id=str(user.id),
        session_id=str(session.id),
        device_fingerprint=fingerprint
    )
    
    refresh_token = token_service.create_refresh_token(
        user_id=str(user.id),
        session_id=str(session.id),
        device_fingerprint=fingerprint
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's active sessions."""
    sessions = await db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.status == SessionStatus.ACTIVE
    ).order_by(UserSession.last_activity.desc()).all()
    
    return [SessionResponse.from_orm(s) for s in sessions]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Revoke a specific session."""
    session = await db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Revoke session
    session.status = SessionStatus.REVOKED
    session.revoked_at = datetime.utcnow()
    session.revoke_reason = "User revoked"
    
    # Blacklist tokens
    await redis_client.setex(
        f"blacklist:access:{session.session_token}",
        settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "1"
    )
    
    await redis_client.setex(
        f"blacklist:refresh:{session.refresh_token}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "1"
    )
    
    await db.commit()
    
    return {"message": "Session revoked successfully"}