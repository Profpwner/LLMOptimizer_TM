"""Cryptographic utilities for token encryption."""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os


def generate_key(password: str, salt: Optional[bytes] = None) -> bytes:
    """Generate encryption key from password."""
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_token(token: str, encryption_key: str) -> str:
    """Encrypt OAuth token."""
    key = generate_key(encryption_key)
    f = Fernet(key)
    encrypted = f.encrypt(token.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_token(encrypted_token: str, encryption_key: str) -> str:
    """Decrypt OAuth token."""
    key = generate_key(encryption_key)
    f = Fernet(key)
    decrypted = f.decrypt(base64.urlsafe_b64decode(encrypted_token))
    return decrypted.decode()