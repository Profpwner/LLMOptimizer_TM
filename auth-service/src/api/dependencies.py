"""API dependencies for auth service."""

from typing import Optional
from datetime import datetime
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.user import User, UserStatus
from ..models.session import UserSession, SessionStatus
from ..security.tokens import TokenService, TokenType


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
token_service = TokenService()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode token
        payload = token_service.verify_token(token, TokenType.ACCESS)
        user_id = payload.sub
        
        if not user_id:
            raise credentials_exception
    except ValueError:
        raise credentials_exception
    
    # Get user
    user = await db.get(User, user_id)
    if not user:
        raise credentials_exception
    
    # Check if user is active
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {user.status}"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_session(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserSession:
    """Get current user session from token."""
    try:
        # Decode token
        payload = token_service.verify_token(token, TokenType.ACCESS)
        session_id = payload.session_id
        
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    # Get session
    session = await db.get(UserSession, session_id)
    if not session or not session.is_active():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )
    
    # Check device fingerprint if provided
    device_fingerprint = request.headers.get("x-device-fingerprint")
    if device_fingerprint and session.device_fingerprint != device_fingerprint:
        # Log suspicious activity
        session.is_suspicious = True
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device mismatch detected"
        )
    
    # Update session activity
    session.last_activity = datetime.utcnow()
    session.request_count += 1
    await db.commit()
    
    return session


async def require_mfa(
    current_user: User = Depends(get_current_user),
    current_session: UserSession = Depends(get_current_session)
) -> User:
    """Require MFA verification for sensitive operations."""
    if current_user.mfa_enabled and not current_session.mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA verification required",
            headers={"X-MFA-Required": "true"}
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current user with admin privileges."""
    # Check if user has admin role
    from ..models.rbac import Role, UserRole
    
    admin_role_query = select(Role).where(
        Role.name.in_(["admin", "super_admin"])
    )
    result = await db.execute(admin_role_query)
    admin_roles = result.scalars().all()
    
    user_has_admin = False
    for role in current_user.roles:
        if role.id in [r.id for r in admin_roles]:
            user_has_admin = True
            break
    
    if not user_has_admin and not current_user.is_system_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


class PermissionChecker:
    """Check user permissions for resources."""
    
    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """Check if user has required permission."""
        # Get user permissions through roles
        has_permission = False
        
        for role in current_user.roles:
            for permission in role.get_all_permissions():
                if (permission.resource_type == self.resource and 
                    permission.allows_action(self.action)):
                    has_permission = True
                    break
            if has_permission:
                break
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.action} on {self.resource}"
            )
        
        return current_user


# Common permission dependencies
require_user_read = PermissionChecker("user", "read")
require_user_write = PermissionChecker("user", "update")
require_user_delete = PermissionChecker("user", "delete")
require_admin_access = PermissionChecker("admin", "access")


def require_permission(permission_name: str):
    """Create a dependency that requires a specific permission."""
    async def check_permission(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        # Check if user has the permission
        has_permission = False
        for role in current_user.roles:
            for permission in role.get_all_permissions():
                if permission.name == permission_name:
                    has_permission = True
                    break
            if has_permission:
                break
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name}"
            )
        
        return current_user
    
    return check_permission


# Alias for backward compatibility
require_admin = get_admin_user
get_session_info = get_current_session


async def verify_csrf_token(request: Request) -> None:
    """Verify CSRF token for state-changing operations."""
    # This is a placeholder - implement CSRF protection as needed
    pass