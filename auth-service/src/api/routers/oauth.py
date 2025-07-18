"""OAuth endpoints for social login."""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ...database import get_db, get_redis
from ...models.user import User, UserStatus
from ...models.oauth import OAuthConnection
from ...oauth.manager import OAuthManager
from ..schemas import OAuthCallbackRequest, OAuthConnectionResponse
from ..dependencies import get_current_active_user

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/providers")
async def list_oauth_providers():
    """List available OAuth providers."""
    oauth_manager = OAuthManager()
    return {
        "providers": [
            {
                "name": provider,
                "display_name": provider.title(),
                "enabled": True
            }
            for provider in oauth_manager.list_providers()
        ]
    }


@router.get("/authorize/{provider}")
async def oauth_authorize(
    provider: str,
    request: Request,
    redirect_uri: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """Initiate OAuth authorization flow."""
    redis_client = await get_redis()
    oauth_manager = OAuthManager(redis_client)
    
    if provider not in oauth_manager.list_providers():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider} not supported"
        )
    
    # Create authorization URL
    try:
        auth_url, state = await oauth_manager.create_authorization_url(
            provider_name=provider,
            user_ip=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            additional_state={
                "redirect_uri": redirect_uri,
                "user_state": state
            }
        )
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/callback/{provider}")
async def oauth_callback(
    provider: str,
    callback_data: OAuthCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback."""
    redis_client = await get_redis()
    oauth_manager = OAuthManager(redis_client)
    
    try:
        # Validate callback
        result = await oauth_manager.validate_callback(
            provider_name=provider,
            state=callback_data.state,
            code=callback_data.code,
            user_ip=request.client.host
        )
        
        user_info = result["user_info"]
        token_data = result["token_data"]
        
        # Check if OAuth connection exists
        oauth_query = select(OAuthConnection).where(
            OAuthConnection.provider == provider,
            OAuthConnection.provider_user_id == user_info.provider_user_id
        )
        oauth_result = await db.execute(oauth_query)
        oauth_connection = oauth_result.scalar_one_or_none()
        
        if oauth_connection:
            # Update existing connection
            oauth_connection.access_token = token_data["access_token"]
            oauth_connection.refresh_token = token_data.get("refresh_token")
            oauth_connection.expires_at = token_data.get("expires_at")
            oauth_connection.last_used_at = datetime.utcnow()
            
            # Get associated user
            user = await db.get(User, oauth_connection.user_id)
            
            if not user or not user.can_login():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is not active"
                )
        else:
            # Check if user exists with this email
            if user_info.email:
                user_query = select(User).where(User.email == user_info.email)
                user_result = await db.execute(user_query)
                user = user_result.scalar_one_or_none()
            else:
                user = None
            
            if not user:
                # Create new user
                user = User(
                    email=user_info.email or f"{user_info.provider_user_id}@{provider}.oauth",
                    username=f"{provider}_{user_info.provider_user_id}",
                    full_name=user_info.name,
                    is_email_verified=user_info.email_verified,
                    status=UserStatus.ACTIVE,
                    password_hash="oauth_only"  # No password for OAuth users
                )
                db.add(user)
                await db.flush()
            
            # Create OAuth connection
            oauth_connection = OAuthConnection(
                user_id=user.id,
                provider=provider,
                provider_user_id=user_info.provider_user_id,
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_at=token_data.get("expires_at"),
                email=user_info.email,
                name=user_info.name,
                given_name=user_info.given_name,
                family_name=user_info.family_name,
                picture_url=user_info.picture_url,
                locale=user_info.locale,
                provider_data=user_info.raw_data
            )
            db.add(oauth_connection)
        
        await db.commit()
        
        # Create session and tokens (similar to regular login)
        # TODO: Generate JWT tokens and create session
        
        return {
            "user_id": str(user.id),
            "provider": provider,
            "message": "OAuth authentication successful"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/connections", response_model=List[OAuthConnectionResponse])
async def get_oauth_connections(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's OAuth connections."""
    query = select(OAuthConnection).where(
        OAuthConnection.user_id == current_user.id
    )
    result = await db.execute(query)
    connections = result.scalars().all()
    
    return [
        OAuthConnectionResponse(
            provider=conn.provider,
            connected_at=conn.connected_at,
            email=conn.email,
            name=conn.name
        )
        for conn in connections
    ]


@router.delete("/connections/{provider}")
async def disconnect_oauth(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Disconnect OAuth provider."""
    # Check if user has password or other auth methods
    if current_user.password_hash == "oauth_only":
        # Check if this is the only OAuth connection
        connections_count = await db.execute(
            select(func.count(OAuthConnection.id)).where(
                OAuthConnection.user_id == current_user.id
            )
        )
        if connections_count.scalar() <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disconnect the only authentication method"
            )
    
    # Find and remove connection
    query = select(OAuthConnection).where(
        OAuthConnection.user_id == current_user.id,
        OAuthConnection.provider == provider
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} connection found"
        )
    
    # Revoke token if possible
    redis_client = await get_redis()
    oauth_manager = OAuthManager(redis_client)
    try:
        await oauth_manager.revoke_token(provider, connection.access_token)
    except Exception:
        pass  # Continue even if revocation fails
    
    # Delete connection
    await db.delete(connection)
    await db.commit()
    
    return {"message": f"Successfully disconnected from {provider}"}


@router.post("/refresh/{provider}")
async def refresh_oauth_token(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Refresh OAuth access token."""
    # Get connection
    query = select(OAuthConnection).where(
        OAuthConnection.user_id == current_user.id,
        OAuthConnection.provider == provider
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()
    
    if not connection or not connection.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} connection with refresh token found"
        )
    
    # Refresh token
    redis_client = await get_redis()
    oauth_manager = OAuthManager(redis_client)
    
    try:
        new_token_data = await oauth_manager.refresh_token(
            provider,
            connection.refresh_token
        )
        
        # Update connection
        connection.access_token = new_token_data["access_token"]
        if "refresh_token" in new_token_data:
            connection.refresh_token = new_token_data["refresh_token"]
        connection.expires_at = new_token_data.get("expires_at")
        
        await db.commit()
        
        return {"message": "Token refreshed successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )