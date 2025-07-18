"""Authentication endpoints."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from ...database import get_db, get_redis
from ...models.user import User, UserStatus
from ...models.session import UserSession, SessionStatus
from ...models.security import LoginAttempt, SecurityEvent, SecurityEventType
from ...security.tokens import TokenService, TokenType
from ...security.passwords import PasswordService
from ...security.device import DeviceFingerprintService
from ...security.rate_limiter import RateLimiter
from ...mfa.manager import MFAManager
from ...config import settings
from ..schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh,
    PasswordReset, PasswordResetConfirm, ErrorResponse
)
from ..dependencies import get_current_user, get_current_session

router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize services
token_service = TokenService()
password_service = PasswordService()
device_service = DeviceFingerprintService()


@router.post("/register", response_model=UserResponse)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Register a new user."""
    # Check if user exists
    existing_user = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    # Validate password
    is_valid, errors = password_service.validate_password(
        user_data.password,
        user_data.email
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid password", "details": errors}
        )
    
    # Create user
    password_hash = password_service.hash_password(user_data.password)
    
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        phone_number=user_data.phone_number,
        password_hash=password_hash,
        status=UserStatus.PENDING_VERIFICATION if settings.ENABLE_EMAIL_VERIFICATION else UserStatus.ACTIVE,
        terms_accepted_at=datetime.utcnow() if user_data.accept_terms else None,
        terms_version="1.0"
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Send verification email if enabled
    if settings.ENABLE_EMAIL_VERIFICATION:
        verification_token = token_service.create_email_verification_token(
            email=user.email,
            user_id=str(user.id)
        )
        # TODO: Send email via email service
    
    # Log security event
    security_event = SecurityEvent(
        user_id=user.id,
        event_type=SecurityEventType.ACCOUNT_CREATED,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    db.add(security_event)
    await db.commit()
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Login with email/username and password."""
    # Rate limiting
    rate_limiter = RateLimiter(redis_client)
    ip_address = request.client.host
    
    # Check if IP is blocked
    if await rate_limiter.is_ip_blocked(ip_address):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please try again later."
        )
    
    # Check rate limit
    allowed, limit_info = await rate_limiter.check_rate_limit(
        key=ip_address,
        limit_type="login"
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {limit_info['retry_after']} seconds."
        )
    
    # Find user by email or username
    user_query = select(User).where(
        (User.email == form_data.username) | (User.username == form_data.username)
    )
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    
    # Log login attempt
    login_attempt = LoginAttempt(
        user_id=user.id if user else None,
        email=form_data.username,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint")
    )
    
    # Verify user and password
    if not user or not password_service.verify_password(form_data.password, user.password_hash):
        login_attempt.status = "failed"
        login_attempt.failure_reason = "Invalid credentials"
        db.add(login_attempt)
        
        # Increment failed attempts
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.status = UserStatus.LOCKED
                user.locked_until = datetime.utcnow() + timedelta(minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES)
                user.lock_reason = "Too many failed login attempts"
                
                # Block IP after multiple failures
                await rate_limiter.block_ip(
                    ip_address,
                    duration_minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES
                )
        
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if user can login
    if not user.can_login():
        login_attempt.status = "blocked"
        login_attempt.failure_reason = f"Account {user.status}"
        db.add(login_attempt)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {user.status}. Please contact support."
        )
    
    # Check if password needs rehashing
    if password_service.needs_rehash(user.password_hash):
        user.password_hash = password_service.hash_password(form_data.password)
    
    # Device fingerprinting
    device_info = device_service.parse_user_agent(request.headers.get("user-agent", ""))
    
    # Create session
    session = UserSession(
        user_id=user.id,
        session_token=token_service.generate_api_key()[0],
        refresh_token=token_service.generate_api_key()[0],
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
        device_type=device_info.get("device_type"),
        browser=device_info.get("browser"),
        browser_version=device_info.get("browser_version"),
        os=device_info.get("os"),
        os_version=device_info.get("os_version"),
        expires_at=datetime.utcnow() + timedelta(hours=settings.SESSION_LIFETIME_HOURS),
        login_method="password"
    )
    
    db.add(session)
    
    # Update user
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = ip_address
    user.failed_login_attempts = 0
    
    # Log successful login
    login_attempt.status = "success"
    db.add(login_attempt)
    
    security_event = SecurityEvent(
        user_id=user.id,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        session_id=session.id
    )
    db.add(security_event)
    
    await db.commit()
    await db.refresh(user)
    
    # Generate tokens
    access_token = token_service.create_access_token(
        user_id=str(user.id),
        session_id=str(session.id),
        device_fingerprint=session.device_fingerprint
    )
    
    refresh_token = token_service.create_refresh_token(
        user_id=str(user.id),
        session_id=str(session.id),
        device_fingerprint=session.device_fingerprint
    )
    
    # Store refresh token in Redis
    await redis_client.setex(
        f"refresh_token:{user.id}:{session.id}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        refresh_token
    )
    
    # Set secure cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        payload = token_service.verify_token(token_data.refresh_token, TokenType.REFRESH)
        user_id = payload.sub
        session_id = payload.session_id
        
        # Verify token in Redis
        stored_token = await redis_client.get(f"refresh_token:{user_id}:{session_id}")
        if not stored_token or stored_token != token_data.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Get user and session
        user = await db.get(User, user_id)
        session = await db.get(UserSession, session_id)
        
        if not user or not session or not session.is_active():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )
        
        # Generate new tokens
        new_access_token = token_service.create_access_token(
            user_id=str(user.id),
            session_id=str(session.id),
            device_fingerprint=session.device_fingerprint
        )
        
        new_refresh_token = token_service.create_refresh_token(
            user_id=str(user.id),
            session_id=str(session.id),
            device_fingerprint=session.device_fingerprint
        )
        
        # Update refresh token in Redis
        await redis_client.setex(
            f"refresh_token:{user.id}:{session.id}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            new_refresh_token
        )
        
        # Update session activity
        session.last_activity = datetime.utcnow()
        await db.commit()
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    current_session: UserSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Logout current session."""
    # Revoke session
    current_session.status = SessionStatus.REVOKED
    current_session.revoked_at = datetime.utcnow()
    current_session.revoke_reason = "User logout"
    
    # Remove refresh token from Redis
    await redis_client.delete(f"refresh_token:{current_user.id}:{current_session.id}")
    
    # Log event
    security_event = SecurityEvent(
        user_id=current_user.id,
        event_type=SecurityEventType.LOGOUT,
        session_id=current_session.id
    )
    db.add(security_event)
    
    await db.commit()
    
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Logout all user sessions."""
    # Get all active sessions
    sessions_query = select(UserSession).where(
        UserSession.user_id == current_user.id,
        UserSession.status == SessionStatus.ACTIVE
    )
    result = await db.execute(sessions_query)
    sessions = result.scalars().all()
    
    # Revoke all sessions
    for session in sessions:
        session.status = SessionStatus.REVOKED
        session.revoked_at = datetime.utcnow()
        session.revoke_reason = "User logout all"
        
        # Remove refresh token
        await redis_client.delete(f"refresh_token:{current_user.id}:{session.id}")
    
    # Log event
    security_event = SecurityEvent(
        user_id=current_user.id,
        event_type=SecurityEventType.LOGOUT,
        description="Logged out from all devices"
    )
    db.add(security_event)
    
    await db.commit()
    
    return {"message": "Successfully logged out from all devices"}


@router.post("/password-reset")
async def request_password_reset(
    request: Request,
    reset_data: PasswordReset,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Request password reset email."""
    # Rate limiting
    rate_limiter = RateLimiter(redis_client)
    allowed, _ = await rate_limiter.check_rate_limit(
        key=request.client.host,
        limit_type="password_reset"
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )
    
    # Find user
    user_query = select(User).where(User.email == reset_data.email)
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    
    # Always return success to prevent user enumeration
    if user:
        # Generate reset token
        reset_token = token_service.create_password_reset_token(
            email=user.email,
            user_id=str(user.id)
        )
        
        # Store token
        user.password_reset_token = reset_token
        user.password_reset_sent_at = datetime.utcnow()
        
        # Log event
        security_event = SecurityEvent(
            user_id=user.id,
            event_type=SecurityEventType.PASSWORD_RESET_REQUESTED,
            ip_address=request.client.host
        )
        db.add(security_event)
        
        await db.commit()
        
        # TODO: Send reset email via email service
    
    return {"message": "If an account exists with this email, you will receive a password reset link."}


@router.post("/password-reset-confirm")
async def confirm_password_reset(
    request: Request,
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Confirm password reset with token."""
    try:
        # Verify token
        payload = token_service.verify_token(reset_data.token, TokenType.PASSWORD_RESET)
        user_id = payload.user_id
        
        # Get user
        user = await db.get(User, user_id)
        if not user or user.password_reset_token != reset_data.token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Validate new password
        is_valid, errors = password_service.validate_password(
            reset_data.new_password,
            user.email
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid password", "details": errors}
            )
        
        # Check password history
        if not password_service.check_password_history(
            reset_data.new_password,
            user.password_history
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password was recently used. Please choose a different password."
            )
        
        # Update password
        new_hash = password_service.hash_password(reset_data.new_password)
        user.password_hash = new_hash
        user.password_changed_at = datetime.utcnow()
        
        # Update password history
        user.password_history = [new_hash] + user.password_history[:settings.PASSWORD_HISTORY_COUNT - 1]
        
        # Clear reset token
        user.password_reset_token = None
        user.password_reset_at = datetime.utcnow()
        
        # Clear failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Revoke all sessions for security
        sessions_query = select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.status == SessionStatus.ACTIVE
        )
        result = await db.execute(sessions_query)
        sessions = result.scalars().all()
        
        for session in sessions:
            session.status = SessionStatus.REVOKED
            session.revoked_at = datetime.utcnow()
            session.revoke_reason = "Password reset"
        
        # Log event
        security_event = SecurityEvent(
            user_id=user.id,
            event_type=SecurityEventType.PASSWORD_RESET_COMPLETED,
            ip_address=request.client.host
        )
        db.add(security_event)
        
        await db.commit()
        
        return {"message": "Password successfully reset. Please login with your new password."}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )


@router.post("/verify-email/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address with token."""
    try:
        # Verify token
        payload = token_service.verify_token(token, TokenType.EMAIL_VERIFICATION)
        user_id = payload.user_id
        
        # Get user
        user = await db.get(User, user_id)
        if not user or user.email_verification_token != token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        # Verify email
        user.is_email_verified = True
        user.email_verified_at = datetime.utcnow()
        user.email_verification_token = None
        
        # Activate account if pending
        if user.status == UserStatus.PENDING_VERIFICATION:
            user.status = UserStatus.ACTIVE
            user.status_changed_at = datetime.utcnow()
        
        await db.commit()
        
        return {"message": "Email successfully verified"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )