"""Multi-Factor Authentication manager."""

from typing import Dict, List, Optional, Any
from datetime import datetime
import secrets

from ..models.mfa import MFAMethod, MFASetup, MFABackupCode
from ..security.passwords import PasswordService
from .totp import TOTPService
from .sms import SMSService
from .email import EmailMFAService


class MFAManager:
    """Manages all MFA methods and operations."""
    
    def __init__(self, db_session, redis_client=None):
        self.db = db_session
        self.redis = redis_client
        
        # Initialize services
        self.totp_service = TOTPService()
        self.sms_service = SMSService()
        self.email_service = EmailMFAService()
        
        # Password service for backup codes
        self.password_service = PasswordService()
    
    async def list_available_methods(self) -> List[Dict[str, Any]]:
        """List available MFA methods based on configuration."""
        methods = []
        
        # TOTP is always available
        methods.append({
            "method": MFAMethod.TOTP,
            "name": "Authenticator App",
            "description": "Use an authenticator app like Google Authenticator or Authy",
            "enabled": True
        })
        
        # Email MFA
        if self.email_service.is_enabled():
            methods.append({
                "method": MFAMethod.EMAIL,
                "name": "Email",
                "description": "Receive verification codes via email",
                "enabled": True
            })
        
        # SMS MFA
        if self.sms_service.is_enabled():
            methods.append({
                "method": MFAMethod.SMS,
                "name": "SMS",
                "description": "Receive verification codes via SMS",
                "enabled": True
            })
        
        # Backup codes
        methods.append({
            "method": MFAMethod.BACKUP_CODES,
            "name": "Backup Codes",
            "description": "Use one-time backup codes for emergency access",
            "enabled": True
        })
        
        return methods
    
    async def setup_mfa(
        self,
        user_id: str,
        method: MFAMethod,
        device_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Setup MFA method for user."""
        if method == MFAMethod.TOTP:
            return await self._setup_totp(user_id, device_name, **kwargs)
        elif method == MFAMethod.SMS:
            return await self._setup_sms(user_id, **kwargs)
        elif method == MFAMethod.EMAIL:
            return await self._setup_email(user_id, **kwargs)
        elif method == MFAMethod.BACKUP_CODES:
            return await self._generate_backup_codes(user_id)
        else:
            raise ValueError(f"Unsupported MFA method: {method}")
    
    async def verify_mfa(
        self,
        user_id: str,
        method: MFAMethod,
        code: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Verify MFA code."""
        # Get MFA setup
        mfa_setup = await self._get_mfa_setup(user_id, method, **kwargs)
        if not mfa_setup:
            return {
                "success": False,
                "error": "MFA not configured"
            }
        
        if method == MFAMethod.TOTP:
            return await self._verify_totp(mfa_setup, code)
        elif method == MFAMethod.SMS:
            return await self._verify_sms(user_id, code, **kwargs)
        elif method == MFAMethod.EMAIL:
            return await self._verify_email(user_id, code, **kwargs)
        elif method == MFAMethod.BACKUP_CODES:
            return await self._verify_backup_code(user_id, code)
        else:
            raise ValueError(f"Unsupported MFA method: {method}")
    
    async def get_user_mfa_methods(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's configured MFA methods."""
        setups = await self.db.query(MFASetup).filter(
            MFASetup.user_id == user_id,
            MFASetup.is_active == True
        ).all()
        
        methods = []
        for setup in setups:
            methods.append({
                "id": str(setup.id),
                "method": setup.method,
                "device_name": setup.device_name,
                "is_primary": setup.is_primary,
                "is_verified": setup.is_verified,
                "created_at": setup.created_at,
                "last_used_at": setup.last_used_at
            })
        
        return methods
    
    async def remove_mfa_method(
        self,
        user_id: str,
        method: MFAMethod,
        setup_id: Optional[str] = None
    ) -> bool:
        """Remove MFA method from user."""
        query = self.db.query(MFASetup).filter(
            MFASetup.user_id == user_id,
            MFASetup.method == method
        )
        
        if setup_id:
            query = query.filter(MFASetup.id == setup_id)
        
        setup = await query.first()
        if setup:
            setup.is_active = False
            await self.db.commit()
            return True
        
        return False
    
    async def _setup_totp(
        self,
        user_id: str,
        device_name: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Setup TOTP for user."""
        # Check if already exists
        existing = await self.db.query(MFASetup).filter(
            MFASetup.user_id == user_id,
            MFASetup.method == MFAMethod.TOTP,
            MFASetup.device_name == device_name,
            MFASetup.is_active == True
        ).first()
        
        if existing:
            return {
                "success": False,
                "error": "TOTP already configured for this device"
            }
        
        # Generate TOTP setup
        totp_data = await self.totp_service.setup_totp(
            user_id=user_id,
            device_name=device_name or "Default",
            email=email
        )
        
        # Create MFA setup record
        mfa_setup = MFASetup(
            user_id=user_id,
            method=MFAMethod.TOTP,
            secret=totp_data["secret"],  # Should be encrypted in production
            device_name=totp_data["device_name"],
            is_verified=False,
            is_active=True
        )
        
        self.db.add(mfa_setup)
        await self.db.commit()
        
        return {
            "success": True,
            "setup_id": str(mfa_setup.id),
            "qr_code": totp_data["qr_code"],
            "secret": totp_data["secret"],
            "backup_codes": totp_data["backup_codes"]
        }
    
    async def _setup_sms(
        self,
        user_id: str,
        phone_number: str
    ) -> Dict[str, Any]:
        """Setup SMS MFA for user."""
        if not self.sms_service.is_enabled():
            return {
                "success": False,
                "error": "SMS service is not enabled"
            }
        
        # Send verification code
        result = await self.sms_service.send_verification_code(
            phone_number=phone_number,
            user_id=user_id,
            purpose="mfa_setup"
        )
        
        if result["success"]:
            # Create temporary setup record
            mfa_setup = MFASetup(
                user_id=user_id,
                method=MFAMethod.SMS,
                phone_number=phone_number,
                is_verified=False,
                is_active=False  # Not active until verified
            )
            
            self.db.add(mfa_setup)
            await self.db.commit()
            
            result["setup_id"] = str(mfa_setup.id)
        
        return result
    
    async def _setup_email(
        self,
        user_id: str,
        email: str
    ) -> Dict[str, Any]:
        """Setup email MFA for user."""
        if not self.email_service.is_enabled():
            return {
                "success": False,
                "error": "Email service is not enabled"
            }
        
        # Send verification code
        result = await self.email_service.send_verification_code(
            email=email,
            user_id=user_id,
            purpose="mfa_setup"
        )
        
        if result["success"]:
            # Create temporary setup record
            mfa_setup = MFASetup(
                user_id=user_id,
                method=MFAMethod.EMAIL,
                email=email,
                is_verified=False,
                is_active=False  # Not active until verified
            )
            
            self.db.add(mfa_setup)
            await self.db.commit()
            
            result["setup_id"] = str(mfa_setup.id)
        
        return result
    
    async def _generate_backup_codes(
        self,
        user_id: str,
        count: int = 8
    ) -> Dict[str, Any]:
        """Generate backup codes for user."""
        # Get or create backup codes setup
        mfa_setup = await self.db.query(MFASetup).filter(
            MFASetup.user_id == user_id,
            MFASetup.method == MFAMethod.BACKUP_CODES
        ).first()
        
        if not mfa_setup:
            mfa_setup = MFASetup(
                user_id=user_id,
                method=MFAMethod.BACKUP_CODES,
                is_verified=True,
                is_active=True
            )
            self.db.add(mfa_setup)
        
        # Delete old backup codes
        await self.db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_id
        ).delete()
        
        # Generate new codes
        codes = self.password_service.generate_recovery_codes(count)
        
        # Store hashed codes
        for code in codes:
            code_hash = self.password_service.hash_password(code)
            backup_code = MFABackupCode(
                user_id=user_id,
                mfa_setup_id=mfa_setup.id,
                code_hash=code_hash
            )
            self.db.add(backup_code)
        
        mfa_setup.backup_codes_generated = True
        mfa_setup.backup_codes_generated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "success": True,
            "backup_codes": codes,
            "generated_at": datetime.utcnow()
        }
    
    async def _verify_totp(
        self,
        mfa_setup: MFASetup,
        code: str
    ) -> Dict[str, Any]:
        """Verify TOTP code."""
        is_valid, offset = self.totp_service.verify_token(
            secret=mfa_setup.secret,
            token=code
        )
        
        if is_valid:
            # Update usage
            mfa_setup.last_used_at = datetime.utcnow()
            mfa_setup.use_count += 1
            
            if not mfa_setup.is_verified:
                mfa_setup.is_verified = True
                mfa_setup.verified_at = datetime.utcnow()
            
            await self.db.commit()
            
            return {
                "success": True,
                "method": MFAMethod.TOTP
            }
        else:
            return {
                "success": False,
                "error": "Invalid code"
            }
    
    async def _verify_sms(
        self,
        user_id: str,
        code: str,
        phone_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify SMS code."""
        # Get phone number from MFA setup if not provided
        if not phone_number:
            mfa_setup = await self.db.query(MFASetup).filter(
                MFASetup.user_id == user_id,
                MFASetup.method == MFAMethod.SMS,
                MFASetup.is_active == True
            ).first()
            
            if not mfa_setup:
                return {
                    "success": False,
                    "error": "SMS MFA not configured"
                }
            
            phone_number = mfa_setup.phone_number
        
        result = await self.sms_service.verify_code(
            phone_number=phone_number,
            code=code,
            purpose="mfa",
            user_id=user_id
        )
        
        if result["success"]:
            # Update MFA setup
            mfa_setup = await self.db.query(MFASetup).filter(
                MFASetup.user_id == user_id,
                MFASetup.method == MFAMethod.SMS,
                MFASetup.phone_number == phone_number
            ).first()
            
            if mfa_setup:
                mfa_setup.last_used_at = datetime.utcnow()
                mfa_setup.use_count += 1
                
                if not mfa_setup.is_verified:
                    mfa_setup.is_verified = True
                    mfa_setup.verified_at = datetime.utcnow()
                    mfa_setup.is_active = True
                
                await self.db.commit()
        
        return result
    
    async def _verify_email(
        self,
        user_id: str,
        code: str,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify email code."""
        # Get email from MFA setup if not provided
        if not email:
            mfa_setup = await self.db.query(MFASetup).filter(
                MFASetup.user_id == user_id,
                MFASetup.method == MFAMethod.EMAIL,
                MFASetup.is_active == True
            ).first()
            
            if not mfa_setup:
                return {
                    "success": False,
                    "error": "Email MFA not configured"
                }
            
            email = mfa_setup.email
        
        result = await self.email_service.verify_code(
            email=email,
            code=code,
            purpose="mfa",
            user_id=user_id
        )
        
        if result["success"]:
            # Update MFA setup
            mfa_setup = await self.db.query(MFASetup).filter(
                MFASetup.user_id == user_id,
                MFASetup.method == MFAMethod.EMAIL,
                MFASetup.email == email
            ).first()
            
            if mfa_setup:
                mfa_setup.last_used_at = datetime.utcnow()
                mfa_setup.use_count += 1
                
                if not mfa_setup.is_verified:
                    mfa_setup.is_verified = True
                    mfa_setup.verified_at = datetime.utcnow()
                    mfa_setup.is_active = True
                
                await self.db.commit()
        
        return result
    
    async def _verify_backup_code(
        self,
        user_id: str,
        code: str
    ) -> Dict[str, Any]:
        """Verify backup code."""
        # Normalize code (remove dashes)
        code = code.replace("-", "")
        
        # Get unused backup codes
        backup_codes = await self.db.query(MFABackupCode).filter(
            MFABackupCode.user_id == user_id,
            MFABackupCode.is_used == False
        ).all()
        
        for backup_code in backup_codes:
            if self.password_service.verify_password(code, backup_code.code_hash):
                # Mark as used
                backup_code.is_used = True
                backup_code.used_at = datetime.utcnow()
                
                await self.db.commit()
                
                # Check remaining codes
                remaining = await self.db.query(MFABackupCode).filter(
                    MFABackupCode.user_id == user_id,
                    MFABackupCode.is_used == False
                ).count()
                
                return {
                    "success": True,
                    "method": MFAMethod.BACKUP_CODES,
                    "remaining_codes": remaining
                }
        
        return {
            "success": False,
            "error": "Invalid backup code"
        }
    
    async def _get_mfa_setup(
        self,
        user_id: str,
        method: MFAMethod,
        **kwargs
    ) -> Optional[MFASetup]:
        """Get MFA setup for user and method."""
        query = self.db.query(MFASetup).filter(
            MFASetup.user_id == user_id,
            MFASetup.method == method,
            MFASetup.is_active == True
        )
        
        # Add additional filters
        if method == MFAMethod.TOTP and "device_name" in kwargs:
            query = query.filter(MFASetup.device_name == kwargs["device_name"])
        
        return await query.first()