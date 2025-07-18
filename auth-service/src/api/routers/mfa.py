"""Multi-Factor Authentication endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.user import User
from ...mfa.manager import MFAManager
from ..schemas import MFASetupRequest, MFASetupResponse, MFAVerifyRequest, MFAMethodResponse
from ..dependencies import get_current_active_user, require_mfa

router = APIRouter(prefix="/mfa", tags=["mfa"])


@router.get("/methods")
async def list_available_mfa_methods(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List available MFA methods."""
    mfa_manager = MFAManager(db)
    return await mfa_manager.list_available_methods()


@router.get("/user-methods", response_model=List[MFAMethodResponse])
async def get_user_mfa_methods(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's configured MFA methods."""
    mfa_manager = MFAManager(db)
    return await mfa_manager.get_user_mfa_methods(str(current_user.id))


@router.post("/setup", response_model=MFASetupResponse)
async def setup_mfa(
    setup_request: MFASetupRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Setup a new MFA method."""
    mfa_manager = MFAManager(db)
    
    try:
        result = await mfa_manager.setup_mfa(
            user_id=str(current_user.id),
            method=setup_request.method,
            device_name=setup_request.device_name,
            phone_number=setup_request.phone_number,
            email=setup_request.email or current_user.email
        )
        
        if not result.get("success", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Setup failed")
            )
        
        return MFASetupResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify")
async def verify_mfa(
    verify_request: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify MFA code."""
    mfa_manager = MFAManager(db)
    
    result = await mfa_manager.verify_mfa(
        user_id=str(current_user.id),
        method=verify_request.method,
        code=verify_request.code
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Verification failed")
        )
    
    # Update user if first MFA method
    if not current_user.mfa_enabled:
        current_user.mfa_enabled = True
        await db.commit()
    
    return {"message": "MFA verified successfully", **result}


@router.delete("/{method}")
async def remove_mfa_method(
    method: str,
    current_user: User = Depends(require_mfa),
    db: AsyncSession = Depends(get_db)
):
    """Remove an MFA method (requires MFA verification)."""
    mfa_manager = MFAManager(db)
    
    # Check if this is the last method
    methods = await mfa_manager.get_user_mfa_methods(str(current_user.id))
    if len(methods) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last MFA method"
        )
    
    success = await mfa_manager.remove_mfa_method(
        user_id=str(current_user.id),
        method=method
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MFA method not found"
        )
    
    return {"message": f"MFA method {method} removed successfully"}


@router.post("/backup-codes/generate")
async def generate_backup_codes(
    current_user: User = Depends(require_mfa),
    db: AsyncSession = Depends(get_db)
):
    """Generate new backup codes (requires MFA verification)."""
    mfa_manager = MFAManager(db)
    
    result = await mfa_manager.setup_mfa(
        user_id=str(current_user.id),
        method="backup_codes"
    )
    
    return {
        "backup_codes": result["backup_codes"],
        "generated_at": result["generated_at"],
        "message": "Store these codes securely. Each code can only be used once."
    }