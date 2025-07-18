"""User management API routes."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.user import User, UserStatus
from ..models.rbac import Role
from ..security.passwords import PasswordService
from .schemas import (
    UserResponse, UserUpdate, UserListResponse,
    PasswordChange, UserSearch, RoleAssignment
)
from .dependencies import get_current_user, require_admin, require_permission

router = APIRouter(prefix="/users", tags=["users"])

password_service = PasswordService()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile."""
    return UserResponse.from_orm(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile."""
    # Update allowed fields
    update_fields = ["full_name", "phone_number", "timezone", "locale", "bio"]
    
    for field in update_fields:
        if hasattr(user_update, field) and getattr(user_update, field) is not None:
            setattr(current_user, field, getattr(user_update, field))
    
    # Update preferences
    if user_update.preferences:
        current_user.preferences = {
            **current_user.preferences,
            **user_update.preferences
        }
    
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    
    return UserResponse.from_orm(current_user)


@router.post("/me/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user password."""
    # Verify current password
    if not password_service.verify_password(
        password_data.current_password,
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if not password_service.validate_password_strength(password_data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password does not meet security requirements"
        )
    
    # Check password history
    if password_service.is_password_in_history(
        password_data.new_password,
        current_user.password_history
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password has been used recently"
        )
    
    # Update password
    new_hash = password_service.hash_password(password_data.new_password)
    current_user.password_hash = new_hash
    current_user.password_changed_at = datetime.utcnow()
    
    # Update password history
    if not current_user.password_history:
        current_user.password_history = []
    
    current_user.password_history.append(current_user.password_hash)
    # Keep last 5 passwords
    current_user.password_history = current_user.password_history[-5:]
    
    await db.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/me/roles", response_model=List[Dict[str, Any]])
async def get_current_user_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user roles and permissions."""
    # Load roles with permissions
    user = await db.query(User).options(
        selectinload(User.roles).selectinload(Role.permissions)
    ).filter(User.id == current_user.id).first()
    
    roles_data = []
    for role in user.roles:
        permissions = [
            {
                "name": perm.name,
                "resource": perm.resource_type,
                "actions": perm.actions
            }
            for perm in role.get_all_permissions()
        ]
        
        roles_data.append({
            "id": str(role.id),
            "name": role.name,
            "display_name": role.display_name,
            "permissions": permissions
        })
    
    return roles_data


# Admin user management routes
@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[UserStatus] = None,
    role: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|updated_at|last_login_at|email|username)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(require_permission("user:list")),
    db: AsyncSession = Depends(get_db)
):
    """List users with filtering and pagination."""
    query = db.query(User)
    
    # Apply filters
    if search:
        search_filter = or_(
            User.email.ilike(f"%{search}%"),
            User.username.ilike(f"%{search}%"),
            User.full_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    if status:
        query = query.filter(User.status == status)
    
    if role:
        query = query.join(User.roles).filter(Role.name == role)
    
    # Count total
    total = await query.count()
    
    # Apply sorting
    sort_column = getattr(User, sort_by)
    if sort_order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Execute query
    users = await query.options(selectinload(User.roles)).all()
    
    return UserListResponse(
        users=[UserResponse.from_orm(u) for u in users],
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_permission("user:read")),
    db: AsyncSession = Depends(get_db)
):
    """Get user details."""
    user = await db.query(User).options(
        selectinload(User.roles)
    ).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(require_permission("user:update")),
    db: AsyncSession = Depends(get_db)
):
    """Update user details."""
    user = await db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_fields = [
        "full_name", "phone_number", "timezone", "locale",
        "bio", "status", "is_email_verified", "is_phone_verified"
    ]
    
    for field in update_fields:
        if hasattr(user_update, field) and getattr(user_update, field) is not None:
            setattr(user, field, getattr(user_update, field))
    
    # Update metadata
    if user_update.metadata:
        user.metadata = {
            **user.metadata,
            **user_update.metadata
        }
    
    user.updated_at = datetime.utcnow()
    user.updated_by = current_user.id
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.from_orm(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_permission("user:delete")),
    db: AsyncSession = Depends(get_db)
):
    """Delete user (soft delete)."""
    user = await db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete
    user.status = UserStatus.SUSPENDED
    user.deleted_at = datetime.utcnow()
    user.deleted_by = current_user.id
    
    await db.commit()
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/lock")
async def lock_user(
    user_id: str,
    reason: str = Query(..., min_length=1),
    duration_hours: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(require_permission("user:update")),
    db: AsyncSession = Depends(get_db)
):
    """Lock user account."""
    user = await db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.status = UserStatus.LOCKED
    user.lock_reason = reason
    
    if duration_hours:
        user.locked_until = datetime.utcnow() + timedelta(hours=duration_hours)
    
    await db.commit()
    
    return {"message": "User locked successfully"}


@router.post("/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    current_user: User = Depends(require_permission("user:update")),
    db: AsyncSession = Depends(get_db)
):
    """Unlock user account."""
    user = await db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.status = UserStatus.ACTIVE
    user.locked_until = None
    user.lock_reason = None
    user.failed_login_attempts = 0
    
    await db.commit()
    
    return {"message": "User unlocked successfully"}


@router.post("/{user_id}/roles")
async def assign_role(
    user_id: str,
    role_assignment: RoleAssignment,
    current_user: User = Depends(require_permission("user:update")),
    db: AsyncSession = Depends(get_db)
):
    """Assign role to user."""
    user = await db.query(User).options(
        selectinload(User.roles)
    ).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    role = await db.query(Role).filter(
        Role.id == role_assignment.role_id
    ).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Check if already assigned
    if role in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role already assigned"
        )
    
    user.roles.append(role)
    await db.commit()
    
    return {"message": "Role assigned successfully"}


@router.delete("/{user_id}/roles/{role_id}")
async def remove_role(
    user_id: str,
    role_id: str,
    current_user: User = Depends(require_permission("user:update")),
    db: AsyncSession = Depends(get_db)
):
    """Remove role from user."""
    user = await db.query(User).options(
        selectinload(User.roles)
    ).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    role = await db.query(Role).filter(Role.id == role_id).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not assigned to user"
        )
    
    user.roles.remove(role)
    await db.commit()
    
    return {"message": "Role removed successfully"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    temporary_password: Optional[str] = None,
    require_change: bool = True,
    current_user: User = Depends(require_permission("user:update")),
    db: AsyncSession = Depends(get_db)
):
    """Reset user password (admin action)."""
    user = await db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate temporary password if not provided
    if not temporary_password:
        temporary_password = password_service.generate_temporary_password()
    
    # Set new password
    user.password_hash = password_service.hash_password(temporary_password)
    user.password_changed_at = datetime.utcnow()
    
    # Set metadata to require password change
    if require_change:
        user.metadata["require_password_change"] = True
    
    await db.commit()
    
    return {
        "message": "Password reset successfully",
        "temporary_password": temporary_password
    }