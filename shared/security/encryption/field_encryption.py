"""Field-level Encryption with AES-256

This module implements field-level encryption for sensitive data using AES-256-GCM
with support for key rotation and integration with key management systems.
"""

import os
import base64
import json
from typing import Any, Dict, Optional, Union, List
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import secrets
import logging
from dataclasses import dataclass
from enum import Enum
import redis
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class KeyProvider(Enum):
    """Supported key providers"""
    LOCAL = "local"
    AWS_KMS = "aws_kms"
    HASHICORP_VAULT = "vault"
    AZURE_KEY_VAULT = "azure_kv"


@dataclass
class EncryptionKey:
    """Encryption key metadata"""
    key_id: str
    key_version: int
    key_material: bytes
    created_at: datetime
    expires_at: Optional[datetime] = None
    algorithm: str = "AES-256-GCM"
    provider: KeyProvider = KeyProvider.LOCAL


class FieldEncryption:
    """Field-level encryption handler with key rotation support"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key_provider: KeyProvider = KeyProvider.LOCAL,
        key_rotation_days: int = 90,
        kms_key_id: Optional[str] = None,
        vault_path: Optional[str] = None
    ):
        self.redis_client = redis_client
        self.key_provider = key_provider
        self.key_rotation_days = key_rotation_days
        self.kms_key_id = kms_key_id
        self.vault_path = vault_path
        self._init_key_provider()
        self._current_key: Optional[EncryptionKey] = None
        self._key_cache: Dict[str, EncryptionKey] = {}
    
    def _init_key_provider(self):
        """Initialize key provider clients"""
        if self.key_provider == KeyProvider.AWS_KMS:
            self.kms_client = boto3.client('kms')
        elif self.key_provider == KeyProvider.HASHICORP_VAULT:
            import hvac
            self.vault_client = hvac.Client(
                url=os.getenv('VAULT_ADDR', 'http://localhost:8200'),
                token=os.getenv('VAULT_TOKEN')
            )
    
    def encrypt_field(
        self,
        data: Any,
        field_name: str,
        context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Encrypt a single field
        
        Args:
            data: Data to encrypt (string, dict, list, etc.)
            field_name: Field name for context
            context: Additional encryption context
            
        Returns:
            Dictionary with encrypted data and metadata
        """
        # Get current encryption key
        key = self._get_current_key()
        
        # Serialize non-string data
        if not isinstance(data, (str, bytes)):
            data = json.dumps(data)
        
        # Convert to bytes if string
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Generate nonce
        nonce = os.urandom(12)  # 96 bits for GCM
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_material),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Add authenticated data
        aad = self._build_aad(field_name, context)
        encryptor.authenticate_additional_data(aad)
        
        # Encrypt data
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Build encrypted field
        encrypted_field = {
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "tag": base64.b64encode(encryptor.tag).decode('utf-8'),
            "key_id": key.key_id,
            "key_version": key.key_version,
            "algorithm": key.algorithm,
            "field_name": field_name,
            "encrypted_at": datetime.utcnow().isoformat(),
            "context": context
        }
        
        return encrypted_field
    
    def decrypt_field(
        self,
        encrypted_data: Dict[str, Any],
        expected_field_name: Optional[str] = None
    ) -> Any:
        """Decrypt a field
        
        Args:
            encrypted_data: Encrypted field data
            expected_field_name: Expected field name for validation
            
        Returns:
            Decrypted data
        """
        # Validate field name if provided
        if expected_field_name and encrypted_data.get("field_name") != expected_field_name:
            raise ValueError(f"Field name mismatch: expected {expected_field_name}, got {encrypted_data.get('field_name')}")
        
        # Get encryption key
        key = self._get_key(encrypted_data["key_id"], encrypted_data["key_version"])
        
        # Decode components
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        nonce = base64.b64decode(encrypted_data["nonce"])
        tag = base64.b64decode(encrypted_data["tag"])
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key.key_material),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Add authenticated data
        aad = self._build_aad(encrypted_data["field_name"], encrypted_data.get("context"))
        decryptor.authenticate_additional_data(aad)
        
        # Decrypt data
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Decode and deserialize if needed
        try:
            data = plaintext.decode('utf-8')
            # Try to deserialize JSON
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        except UnicodeDecodeError:
            # Return raw bytes if not UTF-8
            return plaintext
    
    def encrypt_multiple_fields(
        self,
        data: Dict[str, Any],
        fields_to_encrypt: List[str],
        context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Encrypt multiple fields in a dictionary
        
        Args:
            data: Dictionary containing data
            fields_to_encrypt: List of field names to encrypt
            context: Additional encryption context
            
        Returns:
            Dictionary with encrypted fields
        """
        encrypted_data = data.copy()
        
        for field in fields_to_encrypt:
            if field in data:
                encrypted_data[field] = self.encrypt_field(
                    data[field],
                    field,
                    context
                )
        
        return encrypted_data
    
    def decrypt_multiple_fields(
        self,
        data: Dict[str, Any],
        fields_to_decrypt: List[str]
    ) -> Dict[str, Any]:
        """Decrypt multiple fields in a dictionary
        
        Args:
            data: Dictionary containing encrypted fields
            fields_to_decrypt: List of field names to decrypt
            
        Returns:
            Dictionary with decrypted fields
        """
        decrypted_data = data.copy()
        
        for field in fields_to_decrypt:
            if field in data and isinstance(data[field], dict) and "ciphertext" in data[field]:
                decrypted_data[field] = self.decrypt_field(data[field], field)
        
        return decrypted_data
    
    def rotate_keys(self) -> str:
        """Rotate encryption keys
        
        Returns:
            New key ID
        """
        logger.info("Starting key rotation")
        
        # Generate new key
        new_key = self._generate_key()
        
        # Save new key
        self._save_key(new_key)
        
        # Update current key
        self._current_key = new_key
        
        # Schedule re-encryption of existing data
        self._schedule_reencryption(new_key.key_id)
        
        logger.info(f"Key rotation completed. New key: {new_key.key_id}")
        return new_key.key_id
    
    def _get_current_key(self) -> EncryptionKey:
        """Get current encryption key"""
        if not self._current_key or self._should_rotate_key(self._current_key):
            # Get or generate current key
            key_id = self.redis_client.get("encryption:current_key_id")
            
            if key_id:
                key_id = key_id.decode() if isinstance(key_id, bytes) else key_id
                version = self.redis_client.get(f"encryption:key:{key_id}:version")
                version = int(version) if version else 1
                self._current_key = self._get_key(key_id, version)
            else:
                # Generate first key
                self._current_key = self._generate_key()
                self._save_key(self._current_key)
                self.redis_client.set("encryption:current_key_id", self._current_key.key_id)
        
        return self._current_key
    
    def _get_key(self, key_id: str, version: int) -> EncryptionKey:
        """Get encryption key by ID and version"""
        cache_key = f"{key_id}:{version}"
        
        # Check cache
        if cache_key in self._key_cache:
            return self._key_cache[cache_key]
        
        # Get from provider
        if self.key_provider == KeyProvider.LOCAL:
            key = self._get_local_key(key_id, version)
        elif self.key_provider == KeyProvider.AWS_KMS:
            key = self._get_kms_key(key_id, version)
        elif self.key_provider == KeyProvider.HASHICORP_VAULT:
            key = self._get_vault_key(key_id, version)
        else:
            raise ValueError(f"Unsupported key provider: {self.key_provider}")
        
        # Cache key
        self._key_cache[cache_key] = key
        return key
    
    def _generate_key(self) -> EncryptionKey:
        """Generate new encryption key"""
        key_id = f"key_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}"
        
        if self.key_provider == KeyProvider.LOCAL:
            # Generate 256-bit key
            key_material = secrets.token_bytes(32)
        elif self.key_provider == KeyProvider.AWS_KMS:
            # Generate data key using KMS
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec='AES_256'
            )
            key_material = response['Plaintext']
        elif self.key_provider == KeyProvider.HASHICORP_VAULT:
            # Generate key using Vault
            response = self.vault_client.secrets.transit.generate_data_key(
                name=self.vault_path,
                key_type='aes256-gcm96'
            )
            key_material = base64.b64decode(response['data']['plaintext'])
        else:
            raise ValueError(f"Unsupported key provider: {self.key_provider}")
        
        return EncryptionKey(
            key_id=key_id,
            key_version=1,
            key_material=key_material,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=self.key_rotation_days),
            provider=self.key_provider
        )
    
    def _save_key(self, key: EncryptionKey):
        """Save encryption key"""
        if self.key_provider == KeyProvider.LOCAL:
            # Encrypt key with master key before storing
            master_key = self._get_master_key()
            encrypted_key = self._encrypt_key_material(key.key_material, master_key)
            
            # Store in Redis
            key_data = {
                "key_id": key.key_id,
                "version": key.key_version,
                "encrypted_key": base64.b64encode(encrypted_key).decode('utf-8'),
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "algorithm": key.algorithm,
                "provider": key.provider.value
            }
            
            self.redis_client.set(
                f"encryption:key:{key.key_id}:{key.key_version}",
                json.dumps(key_data)
            )
            self.redis_client.set(f"encryption:key:{key.key_id}:version", key.key_version)
    
    def _get_local_key(self, key_id: str, version: int) -> EncryptionKey:
        """Get local key from Redis"""
        key_data = self.redis_client.get(f"encryption:key:{key_id}:{version}")
        
        if not key_data:
            raise ValueError(f"Key not found: {key_id}:{version}")
        
        data = json.loads(key_data)
        
        # Decrypt key material
        master_key = self._get_master_key()
        encrypted_key = base64.b64decode(data["encrypted_key"])
        key_material = self._decrypt_key_material(encrypted_key, master_key)
        
        return EncryptionKey(
            key_id=data["key_id"],
            key_version=data["version"],
            key_material=key_material,
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None,
            algorithm=data["algorithm"],
            provider=KeyProvider(data["provider"])
        )
    
    def _get_master_key(self) -> bytes:
        """Get or generate master key for key encryption"""
        master_key_file = os.getenv("MASTER_KEY_FILE", "/etc/llmoptimizer/keys/master.key")
        
        if os.path.exists(master_key_file):
            with open(master_key_file, "rb") as f:
                return f.read()
        else:
            # Generate new master key
            master_key = secrets.token_bytes(32)
            os.makedirs(os.path.dirname(master_key_file), exist_ok=True)
            with open(master_key_file, "wb") as f:
                f.write(master_key)
            # Set restrictive permissions
            os.chmod(master_key_file, 0o600)
            return master_key
    
    def _encrypt_key_material(self, key_material: bytes, master_key: bytes) -> bytes:
        """Encrypt key material with master key"""
        nonce = os.urandom(12)
        cipher = Cipher(
            algorithms.AES(master_key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(key_material) + encryptor.finalize()
        
        # Return nonce + tag + ciphertext
        return nonce + encryptor.tag + ciphertext
    
    def _decrypt_key_material(self, encrypted: bytes, master_key: bytes) -> bytes:
        """Decrypt key material with master key"""
        nonce = encrypted[:12]
        tag = encrypted[12:28]
        ciphertext = encrypted[28:]
        
        cipher = Cipher(
            algorithms.AES(master_key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def _build_aad(self, field_name: str, context: Optional[Dict[str, str]]) -> bytes:
        """Build additional authenticated data"""
        aad_data = {
            "field_name": field_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        if context:
            aad_data["context"] = context
        
        return json.dumps(aad_data, sort_keys=True).encode('utf-8')
    
    def _should_rotate_key(self, key: EncryptionKey) -> bool:
        """Check if key should be rotated"""
        if key.expires_at and datetime.utcnow() > key.expires_at:
            return True
        
        # Check key age
        key_age = datetime.utcnow() - key.created_at
        return key_age.days >= self.key_rotation_days
    
    def _schedule_reencryption(self, new_key_id: str):
        """Schedule re-encryption of existing data with new key"""
        # This would typically trigger a background job
        # For now, we'll just log it
        logger.info(f"Scheduled re-encryption with key: {new_key_id}")
        
        # Store re-encryption task
        task = {
            "task_id": f"reencrypt_{new_key_id}_{datetime.utcnow().timestamp()}",
            "new_key_id": new_key_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.redis_client.lpush("encryption:reencryption_tasks", json.dumps(task))