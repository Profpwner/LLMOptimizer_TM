"""Admin endpoints for user and role management."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from ...database import get_db
from ...models.user import User, UserStatus
from ...models.rbac import Role, Permission
from ..schemas import UserResponse, RoleCreate, RoleResponse, UserRoleUpdate
from ..dependencies import get_admin_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[UserStatus] = None,
    search: Optional[str] = None,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)."""
    query = select(User)
    
    if status:
        query = query.where(User.status == status)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user details (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status: UserStatus,
    reason: Optional[str] = None,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user status (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.status = status
    user.status_changed_at = datetime.utcnow()
    user.status_reason = reason
    
    await db.commit()
    
    return {"message": f"User status updated to {status}"}


@router.post("/users/{user_id}/unlock")
async def unlock_user_account(
    user_id: str,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Unlock user account (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.failed_login_attempts = 0
    user.locked_until = None
    user.lock_reason = None
    
    if user.status == UserStatus.LOCKED:
        user.status = UserStatus.ACTIVE
        user.status_changed_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "User account unlocked"}


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all roles (admin only)."""
    query = select(Role)
    result = await db.execute(query)
    roles = result.scalars().all()
    
    # Get user counts for each role
    role_responses = []
    for role in roles:
        user_count_query = select(func.count()).select_from(User).where(
            User.roles.any(Role.id == role.id)
        )
        user_count_result = await db.execute(user_count_query)
        user_count = user_count_result.scalar()
        
        role_response = RoleResponse(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            is_system_role=role.is_system_role,
            permissions=[p.name for p in role.permissions],
            user_count=user_count
        )
        role_responses.append(role_response)
    
    return role_responses


@router.post("/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new role (admin only)."""
    # Check if role exists
    existing_query = select(Role).where(Role.name == role_data.name)
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )
    
    # Create role
    role = Role(
        name=role_data.name,
        display_name=role_data.display_name,
        description=role_data.description,
        is_custom_role=True,
        created_by=current_admin.id
    )
    
    # Add permissions
    if role_data.permissions:
        permissions_query = select(Permission).where(
            Permission.name.in_(role_data.permissions)
        )
        permissions_result = await db.execute(permissions_query)
        permissions = permissions_result.scalars().all()
        role.permissions = permissions
    
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return RoleResponse(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        permissions=[p.name for p in role.permissions],
        user_count=0
    )


@router.put("/users/{user_id}/roles")
async def update_user_roles(
    user_id: str,
    role_update: UserRoleUpdate,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user roles (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get roles
    roles_query = select(Role).where(Role.id.in_(role_update.role_ids))
    roles_result = await db.execute(roles_query)
    roles = roles_result.scalars().all()
    
    # Update user roles
    user.roles = roles
    await db.commit()
    
    return {
        "message": "User roles updated",
        "roles": [r.name for r in roles]
    }


@router.get("/stats")
async def get_admin_stats(
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics."""
    # User stats
    total_users = await db.execute(select(func.count(User.id)))
    active_users = await db.execute(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )
    
    # Get stats from last 24 hours
    from datetime import timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    new_users_24h = await db.execute(
        select(func.count(User.id)).where(User.created_at >= yesterday)
    )
    
    # Active sessions (simplified - would need session tracking)
    from ...models.session import UserSession
    active_sessions = await db.execute(
        select(func.count(UserSession.id)).where(
            UserSession.status == "active",
            UserSession.expires_at > datetime.utcnow()
        )
    )
    
    return {
        "users": {
            "total": total_users.scalar(),
            "active": active_users.scalar(),
            "new_24h": new_users_24h.scalar()
        },
        "sessions": {
            "active": active_sessions.scalar()
        }
    }