"""JWT Token Handler with Refresh Token Support

This module implements secure JWT token generation and validation with refresh token support.
Follows OWASP security guidelines for JWT implementation.
"""

import os
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple, Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import redis
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class JWTHandler:
    """Secure JWT token handler with refresh token support"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 30,
        algorithm: str = "RS256",
        issuer: str = "llmoptimizer",
        audience: str = "llmoptimizer-api"
    ):
        self.redis_client = redis_client
        self.access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)
        self.algorithm = algorithm
        self.issuer = issuer
        self.audience = audience
        self._load_or_generate_keys()
        
    def _load_or_generate_keys(self):
        """Load or generate RSA key pair for JWT signing"""
        private_key_path = os.getenv("JWT_PRIVATE_KEY_PATH", "/etc/llmoptimizer/keys/jwt_private.pem")
        public_key_path = os.getenv("JWT_PUBLIC_KEY_PATH", "/etc/llmoptimizer/keys/jwt_public.pem")
        
        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            with open(public_key_path, "rb") as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend()
                )
        else:
            # Generate new key pair
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
                backend=default_backend()
            )
            self.public_key = self.private_key.public_key()
            
            # Save keys if paths are writable
            os.makedirs(os.path.dirname(private_key_path), exist_ok=True)
            os.makedirs(os.path.dirname(public_key_path), exist_ok=True)
            
            with open(private_key_path, "wb") as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            with open(public_key_path, "wb") as f:
                f.write(self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
    
    def generate_tokens(
        self,
        user_id: str,
        claims: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Generate access and refresh tokens
        
        Args:
            user_id: User identifier
            claims: Additional claims to include in the token
            device_id: Device identifier for device-specific tokens
            
        Returns:
            Tuple of (access_token, refresh_token, token_info)
        """
        now = datetime.now(timezone.utc)
        jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        
        # Base payload
        base_payload = {
            "sub": user_id,
            "iat": now,
            "iss": self.issuer,
            "aud": self.audience,
            "device_id": device_id
        }
        
        # Add custom claims
        if claims:
            base_payload.update(claims)
        
        # Access token payload
        access_payload = {
            **base_payload,
            "exp": now + self.access_token_expire,
            "jti": jti,
            "type": "access"
        }
        
        # Refresh token payload
        refresh_payload = {
            "sub": user_id,
            "exp": now + self.refresh_token_expire,
            "jti": refresh_jti,
            "type": "refresh",
            "access_jti": jti,
            "device_id": device_id,
            "iat": now,
            "iss": self.issuer,
            "aud": self.audience
        }
        
        # Generate tokens
        access_token = jwt.encode(
            access_payload,
            self.private_key,
            algorithm=self.algorithm,
            headers={"kid": self._get_key_id()}
        )
        
        refresh_token = jwt.encode(
            refresh_payload,
            self.private_key,
            algorithm=self.algorithm,
            headers={"kid": self._get_key_id()}
        )
        
        # Store refresh token in Redis
        self._store_refresh_token(refresh_jti, user_id, device_id, access_jti)
        
        token_info = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": int(self.access_token_expire.total_seconds()),
            "refresh_expires_in": int(self.refresh_token_expire.total_seconds()),
            "issued_at": now.isoformat()
        }
        
        return access_token, refresh_token, token_info
    
    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode access token
        
        Args:
            token: JWT access token
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "sub", "jti", "type"]}
            )
            
            # Verify token type
            if payload.get("type") != "access":
                logger.warning(f"Invalid token type: {payload.get('type')}")
                return None
            
            # Check if token is blacklisted
            if self._is_token_blacklisted(payload["jti"]):
                logger.warning(f"Blacklisted token used: {payload['jti']}")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Generate new access token using refresh token
        
        Args:
            refresh_token: JWT refresh token
            
        Returns:
            Tuple of (new_access_token, new_refresh_token, token_info) or None if invalid
        """
        try:
            payload = jwt.decode(
                refresh_token,
                self.public_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "sub", "jti", "type"]}
            )
            
            # Verify token type
            if payload.get("type") != "refresh":
                logger.warning(f"Invalid token type for refresh: {payload.get('type')}")
                return None
            
            # Check if refresh token exists in Redis
            if not self._validate_refresh_token(payload["jti"], payload["sub"]):
                logger.warning(f"Invalid refresh token: {payload['jti']}")
                return None
            
            # Blacklist old access token
            if "access_jti" in payload:
                self._blacklist_token(payload["access_jti"])
            
            # Generate new tokens
            return self.generate_tokens(
                user_id=payload["sub"],
                device_id=payload.get("device_id")
            )
            
        except jwt.ExpiredSignatureError:
            logger.debug("Refresh token expired")
            # Clean up expired refresh token
            if "jti" in locals() and "sub" in locals():
                self._revoke_refresh_token(payload["jti"], payload["sub"])
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid refresh token: {str(e)}")
            return None
    
    def revoke_tokens(self, user_id: str, device_id: Optional[str] = None):
        """Revoke all tokens for a user or specific device
        
        Args:
            user_id: User identifier
            device_id: Optional device identifier to revoke specific device tokens
        """
        pattern = f"refresh_token:{user_id}:*"
        if device_id:
            pattern = f"refresh_token:{user_id}:{device_id}:*"
        
        # Find and delete all matching refresh tokens
        for key in self.redis_client.scan_iter(match=pattern):
            token_data = self.redis_client.get(key)
            if token_data:
                data = eval(token_data)  # Safe since we control the data
                if "access_jti" in data:
                    self._blacklist_token(data["access_jti"])
            self.redis_client.delete(key)
    
    def _store_refresh_token(self, jti: str, user_id: str, device_id: Optional[str], access_jti: str):
        """Store refresh token in Redis"""
        key = f"refresh_token:{user_id}:{device_id or 'default'}:{jti}"
        value = {
            "jti": jti,
            "access_jti": access_jti,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.redis_client.setex(
            key,
            self.refresh_token_expire,
            str(value)
        )
    
    def _validate_refresh_token(self, jti: str, user_id: str) -> bool:
        """Validate refresh token exists in Redis"""
        pattern = f"refresh_token:{user_id}:*:{jti}"
        for key in self.redis_client.scan_iter(match=pattern):
            return True
        return False
    
    def _revoke_refresh_token(self, jti: str, user_id: str):
        """Revoke specific refresh token"""
        pattern = f"refresh_token:{user_id}:*:{jti}"
        for key in self.redis_client.scan_iter(match=pattern):
            self.redis_client.delete(key)
    
    def _blacklist_token(self, jti: str):
        """Add token to blacklist"""
        key = f"blacklist:{jti}"
        # Set with expiration matching access token lifetime
        self.redis_client.setex(
            key,
            self.access_token_expire,
            "1"
        )
    
    def _is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        return bool(self.redis_client.get(f"blacklist:{jti}"))
    
    @lru_cache(maxsize=1)
    def _get_key_id(self) -> str:
        """Get key ID for JWT header"""
        # Generate a stable key ID from public key
        key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        import hashlib
        return hashlib.sha256(key_bytes).hexdigest()[:16]
    
    def get_public_key_jwks(self) -> Dict[str, Any]:
        """Get public key in JWKS format for external validation"""
        from cryptography.hazmat.primitives.asymmetric import rsa
        
        public_numbers = self.public_key.public_numbers()
        
        # Convert to base64url encoding
        import base64
        
        def int_to_base64url(n: int) -> str:
            # Convert integer to bytes
            byte_length = (n.bit_length() + 7) // 8
            bytes_data = n.to_bytes(byte_length, 'big')
            # Encode to base64url
            return base64.urlsafe_b64encode(bytes_data).rstrip(b'=').decode('ascii')
        
        return {
            "keys": [{
                "kty": "RSA",
                "use": "sig",
                "kid": self._get_key_id(),
                "alg": self.algorithm,
                "n": int_to_base64url(public_numbers.n),
                "e": int_to_base64url(public_numbers.e)
            }]
        }