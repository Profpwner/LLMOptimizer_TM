"""User management endpoints."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from ...database import get_db
from ...models.user import User, UserStatus
from ...models.session import UserSession
from ...security.passwords import PasswordService
from ..schemas import (
    UserResponse, UserUpdate, PasswordChange, SessionResponse
)
from ..dependencies import get_current_user, get_current_active_user, require_mfa

router = APIRouter(prefix="/users", tags=["users"])
password_service = PasswordService()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile."""
    # Update allowed fields
    update_fields = user_update.dict(exclude_unset=True)
    for field, value in update_fields.items():
        if hasattr(current_user, field):
            setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/me/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(require_mfa),
    db: AsyncSession = Depends(get_db)
):
    """Change user password (requires MFA if enabled)."""
    # Verify current password
    if not password_service.verify_password(
        password_data.current_password,
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    is_valid, errors = password_service.validate_password(
        password_data.new_password,
        current_user.email
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid password", "details": errors}
        )
    
    # Check password history
    if not password_service.check_password_history(
        password_data.new_password,
        current_user.password_history
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password was recently used. Please choose a different password."
        )
    
    # Update password
    new_hash = password_service.hash_password(password_data.new_password)
    current_user.password_hash = new_hash
    current_user.password_changed_at = datetime.utcnow()
    
    # Update password history
    current_user.password_history = [new_hash] + current_user.password_history[:4]
    
    await db.commit()
    
    # TODO: Send notification email
    
    return {"message": "Password successfully changed"}


@router.get("/me/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(True, description="Show only active sessions")
):
    """Get user's sessions."""
    query = select(UserSession).where(
        UserSession.user_id == current_user.id
    )
    
    if active_only:
        query = query.where(UserSession.status == "active")
    
    query = query.order_by(UserSession.created_at.desc())
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    # Mark current session
    # TODO: Get current session ID from token
    
    return [
        SessionResponse(
            id=session.id,
            device_type=session.device_type,
            device_name=session.device_name,
            browser=session.browser,
            os=session.os,
            ip_address=session.ip_address,
            location=session.location,
            created_at=session.created_at,
            last_activity=session.last_activity,
            is_current=False  # TODO: Set based on current session
        )
        for session in sessions
    ]


@router.delete("/me/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke a specific session."""
    # Get session
    session = await db.get(UserSession, session_id)
    
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Revoke session
    session.status = "revoked"
    session.revoked_at = datetime.utcnow()
    session.revoke_reason = "User revoked"
    
    await db.commit()
    
    return {"message": "Session revoked successfully"}


@router.delete("/me")
async def delete_account(
    current_user: User = Depends(require_mfa),
    db: AsyncSession = Depends(get_db)
):
    """Delete user account (requires MFA)."""
    # Soft delete - mark as deleted but keep data
    current_user.status = UserStatus.SUSPENDED
    current_user.status_changed_at = datetime.utcnow()
    current_user.status_reason = "User requested deletion"
    
    # Revoke all sessions
    sessions_query = select(UserSession).where(
        UserSession.user_id == current_user.id,
        UserSession.status == "active"
    )
    result = await db.execute(sessions_query)
    sessions = result.scalars().all()
    
    for session in sessions:
        session.status = "revoked"
        session.revoked_at = datetime.utcnow()
        session.revoke_reason = "Account deletion"
    
    await db.commit()
    
    # TODO: Schedule permanent deletion after grace period
    # TODO: Send confirmation email
    
    return {"message": "Account scheduled for deletion"}


@router.post("/me/verify-phone")
async def request_phone_verification(
    phone_number: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Request phone number verification."""
    # TODO: Implement phone verification
    return {"message": "Verification code sent"}


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search for users (requires authentication)."""
    # Basic search by username, email, or full name
    search_pattern = f"%{q}%"
    
    query = select(User).where(
        or_(
            User.username.ilike(search_pattern),
            User.email.ilike(search_pattern),
            User.full_name.ilike(search_pattern)
        ),
        User.status == UserStatus.ACTIVE
    ).limit(limit).offset(offset)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Return limited information for privacy
    return [
        {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url
        }
        for user in users
    ]