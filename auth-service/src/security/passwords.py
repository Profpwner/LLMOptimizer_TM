"""Password hashing and validation service."""

import re
import secrets
import string
from typing import List, Tuple, Optional
from datetime import datetime, timedelta

from passlib.context import CryptContext
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

from ..config import settings


class PasswordService:
    """Service for password hashing and validation."""
    
    def __init__(self):
        # Use bcrypt as primary with argon2 as fallback
        self.pwd_context = CryptContext(
            schemes=["bcrypt", "argon2"],
            deprecated="auto",
            bcrypt__rounds=12,
            argon2__memory_cost=65536,
            argon2__time_cost=3,
            argon2__parallelism=4
        )
        
        # Argon2 for new passwords (more secure)
        self.argon2 = PasswordHasher(
            memory_cost=65536,
            time_cost=3,
            parallelism=4
        )
        
        # Password policy from settings
        self.min_length = settings.PASSWORD_MIN_LENGTH
        self.require_uppercase = settings.PASSWORD_REQUIRE_UPPERCASE
        self.require_lowercase = settings.PASSWORD_REQUIRE_LOWERCASE
        self.require_digits = settings.PASSWORD_REQUIRE_DIGITS
        self.require_special = settings.PASSWORD_REQUIRE_SPECIAL
        self.history_count = settings.PASSWORD_HISTORY_COUNT
        
        # Common passwords list (in production, load from file)
        self.common_passwords = {
            "password", "123456", "password123", "admin", "letmein",
            "qwerty", "123456789", "12345678", "12345", "1234567",
            "welcome", "monkey", "dragon", "baseball", "football"
        }
        
    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2."""
        return self.argon2.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        try:
            # Try Argon2 first
            if hashed_password.startswith("$argon2"):
                self.argon2.verify(hashed_password, plain_password)
                return True
        except (VerifyMismatchError, InvalidHash):
            pass
        
        # Fall back to passlib context (supports multiple schemes)
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False
    
    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if password needs rehashing with newer algorithm."""
        if hashed_password.startswith("$argon2"):
            try:
                return self.argon2.check_needs_rehash(hashed_password)
            except Exception:
                return True
        # Non-argon2 hashes should be upgraded
        return True
    
    def validate_password(self, password: str, email: Optional[str] = None) -> Tuple[bool, List[str]]:
        """Validate password against policy."""
        errors = []
        
        # Check length
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        
        # Check character requirements
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.require_digits and not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")
        
        if self.require_special and not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
            errors.append("Password must contain at least one special character")
        
        # Check common passwords
        if password.lower() in self.common_passwords:
            errors.append("Password is too common. Please choose a more unique password")
        
        # Check if password contains email parts
        if email:
            email_parts = email.lower().split('@')[0].split('.')
            for part in email_parts:
                if len(part) > 3 and part in password.lower():
                    errors.append("Password should not contain parts of your email address")
                    break
        
        # Check for repeated characters
        if re.search(r"(.)\1{2,}", password):
            errors.append("Password should not contain repeated characters")
        
        # Check for sequential characters
        if self._has_sequential_chars(password):
            errors.append("Password should not contain sequential characters")
        
        return len(errors) == 0, errors
    
    def check_password_history(self, password: str, password_history: List[str]) -> bool:
        """Check if password was used recently."""
        if not password_history:
            return True
        
        # Check against recent passwords
        recent_passwords = password_history[:self.history_count]
        for old_hash in recent_passwords:
            if self.verify_password(password, old_hash):
                return False
        
        return True
    
    def generate_secure_password(self, length: int = 16) -> str:
        """Generate a secure random password."""
        # Ensure minimum length
        length = max(length, self.min_length)
        
        # Character sets
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        # Start with required characters
        password_chars = []
        if self.require_uppercase:
            password_chars.append(secrets.choice(uppercase))
        if self.require_lowercase:
            password_chars.append(secrets.choice(lowercase))
        if self.require_digits:
            password_chars.append(secrets.choice(digits))
        if self.require_special:
            password_chars.append(secrets.choice(special))
        
        # Fill remaining length with random characters
        all_chars = uppercase + lowercase + digits + special
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    def calculate_password_strength(self, password: str) -> Tuple[int, str]:
        """Calculate password strength score (0-100) and label."""
        score = 0
        
        # Length score (max 30 points)
        length_score = min(30, len(password) * 2)
        score += length_score
        
        # Character variety (max 40 points)
        variety_score = 0
        if re.search(r"[a-z]", password):
            variety_score += 10
        if re.search(r"[A-Z]", password):
            variety_score += 10
        if re.search(r"\d", password):
            variety_score += 10
        if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
            variety_score += 10
        score += variety_score
        
        # Complexity bonus (max 30 points)
        complexity_score = 0
        
        # No common passwords
        if password.lower() not in self.common_passwords:
            complexity_score += 10
        
        # No repeated characters
        if not re.search(r"(.)\1{2,}", password):
            complexity_score += 10
        
        # No sequential characters
        if not self._has_sequential_chars(password):
            complexity_score += 10
        
        score += complexity_score
        
        # Determine strength label
        if score >= 80:
            strength = "Very Strong"
        elif score >= 60:
            strength = "Strong"
        elif score >= 40:
            strength = "Moderate"
        elif score >= 20:
            strength = "Weak"
        else:
            strength = "Very Weak"
        
        return score, strength
    
    def _has_sequential_chars(self, password: str) -> bool:
        """Check for sequential characters like 'abc' or '123'."""
        sequences = [
            "abcdefghijklmnopqrstuvwxyz",
            "0123456789",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm"
        ]
        
        password_lower = password.lower()
        for seq in sequences:
            for i in range(len(seq) - 2):
                if seq[i:i+3] in password_lower:
                    return True
                # Check reverse too
                if seq[i:i+3][::-1] in password_lower:
                    return True
        
        return False
    
    @staticmethod
    def generate_recovery_codes(count: int = 8) -> List[str]:
        """Generate recovery codes for account recovery."""
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric codes
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            # Format as XXXX-XXXX for readability
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        return codes