"""Security Utilities

Common security utilities for password policies, session management,
IP allowlisting/blocklisting, and threat detection.
"""

import re
import secrets
import string
import hashlib
import ipaddress
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
import redis
import bcrypt
from zxcvbn import zxcvbn
import geoip2.database
import logging
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class PasswordPolicy:
    """Password policy configuration"""
    min_length: int = 12
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special: bool = True
    min_unique_chars: int = 5
    prevent_common_passwords: bool = True
    prevent_user_info: bool = True
    history_count: int = 5  # Number of previous passwords to check
    min_strength_score: int = 3  # zxcvbn score (0-4)
    expiry_days: Optional[int] = 90
    special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"


class PasswordValidator:
    """Password validation and policy enforcement"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        policy: Optional[PasswordPolicy] = None,
        common_passwords_file: Optional[str] = None
    ):
        self.redis_client = redis_client
        self.policy = policy or PasswordPolicy()
        self.common_passwords = self._load_common_passwords(common_passwords_file)
    
    def _load_common_passwords(self, file_path: Optional[str]) -> Set[str]:
        """Load common passwords list"""
        if not file_path:
            # Default common passwords
            return {
                "password", "123456", "password123", "admin", "letmein",
                "welcome", "monkey", "dragon", "baseball", "iloveyou",
                "trustno1", "1234567", "sunshine", "master", "123456789",
                "welcome123", "shadow", "ashley", "football", "jesus",
                "michael", "ninja", "mustang", "password1"
            }
        
        try:
            with open(file_path, 'r') as f:
                return set(line.strip().lower() for line in f)
        except Exception as e:
            logger.warning(f"Failed to load common passwords file: {str(e)}")
            return set()
    
    def validate_password(
        self,
        password: str,
        user_info: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Validate password against policy
        
        Args:
            password: Password to validate
            user_info: User information (username, email, etc.) to check against
            user_id: User ID for history check
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Length check
        if len(password) < self.policy.min_length:
            errors.append(f"Password must be at least {self.policy.min_length} characters long")
        
        if len(password) > self.policy.max_length:
            errors.append(f"Password must not exceed {self.policy.max_length} characters")
        
        # Character requirements
        if self.policy.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.policy.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.policy.require_digits and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if self.policy.require_special and not re.search(f'[{re.escape(self.policy.special_chars)}]', password):
            errors.append("Password must contain at least one special character")
        
        # Unique characters check
        if len(set(password)) < self.policy.min_unique_chars:
            errors.append(f"Password must contain at least {self.policy.min_unique_chars} unique characters")
        
        # Common passwords check
        if self.policy.prevent_common_passwords and password.lower() in self.common_passwords:
            errors.append("Password is too common")
        
        # User info check
        if self.policy.prevent_user_info and user_info:
            for key, value in user_info.items():
                if value and len(value) > 3 and value.lower() in password.lower():
                    errors.append(f"Password must not contain your {key}")
        
        # Password strength check
        strength = zxcvbn(password, user_inputs=list(user_info.values()) if user_info else None)
        if strength['score'] < self.policy.min_strength_score:
            errors.append(f"Password is too weak. {strength['feedback']['warning'] or 'Try a more complex password'}")
            if strength['feedback']['suggestions']:
                errors.extend(strength['feedback']['suggestions'])
        
        # History check
        if user_id and self.policy.history_count > 0:
            if self._is_password_in_history(user_id, password):
                errors.append(f"Password was used recently. Please choose a different password")
        
        return len(errors) == 0, errors
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    
    def generate_secure_password(
        self,
        length: Optional[int] = None,
        exclude_ambiguous: bool = True
    ) -> str:
        """Generate a secure random password"""
        length = length or max(16, self.policy.min_length)
        
        # Character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = self.policy.special_chars
        
        # Exclude ambiguous characters if requested
        if exclude_ambiguous:
            ambiguous = 'il1Lo0O'
            lowercase = ''.join(c for c in lowercase if c not in ambiguous)
            uppercase = ''.join(c for c in uppercase if c not in ambiguous)
            digits = ''.join(c for c in digits if c not in ambiguous)
        
        # Ensure password meets requirements
        password_chars = []
        
        if self.policy.require_lowercase:
            password_chars.append(secrets.choice(lowercase))
        if self.policy.require_uppercase:
            password_chars.append(secrets.choice(uppercase))
        if self.policy.require_digits:
            password_chars.append(secrets.choice(digits))
        if self.policy.require_special:
            password_chars.append(secrets.choice(special))
        
        # Fill remaining length
        all_chars = lowercase + uppercase + digits + special
        remaining_length = length - len(password_chars)
        password_chars.extend(secrets.choice(all_chars) for _ in range(remaining_length))
        
        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    def add_password_to_history(self, user_id: str, password_hash: str):
        """Add password hash to user's history"""
        key = f"password:history:{user_id}"
        
        # Add to list
        self.redis_client.lpush(key, password_hash)
        
        # Trim to history limit
        self.redis_client.ltrim(key, 0, self.policy.history_count - 1)
        
        # Set expiry
        self.redis_client.expire(key, 86400 * 365)  # 1 year
    
    def _is_password_in_history(self, user_id: str, password: str) -> bool:
        """Check if password was used recently"""
        key = f"password:history:{user_id}"
        history = self.redis_client.lrange(key, 0, -1)
        
        for old_hash in history:
            if isinstance(old_hash, bytes):
                old_hash = old_hash.decode('utf-8')
            if self.verify_password(password, old_hash):
                return True
        
        return False
    
    def check_password_expiry(self, user_id: str, last_changed: datetime) -> bool:
        """Check if password has expired"""
        if not self.policy.expiry_days:
            return False
        
        expiry_date = last_changed + timedelta(days=self.policy.expiry_days)
        return datetime.utcnow() > expiry_date


class SessionManager:
    """Secure session management"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        session_timeout: int = 3600,  # 1 hour
        absolute_timeout: int = 28800,  # 8 hours
        concurrent_sessions: int = 5,
        enable_fingerprinting: bool = True
    ):
        self.redis_client = redis_client
        self.session_timeout = session_timeout
        self.absolute_timeout = absolute_timeout
        self.concurrent_sessions = concurrent_sessions
        self.enable_fingerprinting = enable_fingerprinting
    
    def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        device_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create new session"""
        # Generate session ID
        session_id = secrets.token_urlsafe(32)
        
        # Create fingerprint
        fingerprint = self._generate_fingerprint(ip_address, user_agent, device_id)
        
        # Session data
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_id": device_id,
            "fingerprint": fingerprint,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Store session
        key = f"session:{session_id}"
        self.redis_client.setex(
            key,
            self.session_timeout,
            json.dumps(session_data)
        )
        
        # Add to user's session list
        user_sessions_key = f"user:sessions:{user_id}"
        self.redis_client.zadd(
            user_sessions_key,
            {session_id: datetime.utcnow().timestamp()}
        )
        
        # Enforce concurrent session limit
        self._enforce_session_limit(user_id)
        
        # Log session creation
        logger.info(f"Session created for user {user_id}: {session_id}")
        
        return session_id
    
    def validate_session(
        self,
        session_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate and refresh session"""
        key = f"session:{session_id}"
        session_data = self.redis_client.get(key)
        
        if not session_data:
            return None
        
        session = json.loads(session_data)
        
        # Check absolute timeout
        created_at = datetime.fromisoformat(session['created_at'])
        if (datetime.utcnow() - created_at).total_seconds() > self.absolute_timeout:
            self.destroy_session(session_id)
            return None
        
        # Validate fingerprint if enabled
        if self.enable_fingerprinting and ip_address and user_agent:
            fingerprint = self._generate_fingerprint(ip_address, user_agent, device_id)
            if fingerprint != session['fingerprint']:
                logger.warning(f"Session fingerprint mismatch: {session_id}")
                # Could be stricter and invalidate session
                # self.destroy_session(session_id)
                # return None
        
        # Update last activity
        session['last_activity'] = datetime.utcnow().isoformat()
        
        # Refresh session
        self.redis_client.setex(
            key,
            self.session_timeout,
            json.dumps(session)
        )
        
        return session
    
    def destroy_session(self, session_id: str):
        """Destroy session"""
        key = f"session:{session_id}"
        session_data = self.redis_client.get(key)
        
        if session_data:
            session = json.loads(session_data)
            user_id = session.get('user_id')
            
            # Remove session
            self.redis_client.delete(key)
            
            # Remove from user's session list
            if user_id:
                user_sessions_key = f"user:sessions:{user_id}"
                self.redis_client.zrem(user_sessions_key, session_id)
            
            logger.info(f"Session destroyed: {session_id}")
    
    def destroy_all_user_sessions(self, user_id: str):
        """Destroy all sessions for a user"""
        user_sessions_key = f"user:sessions:{user_id}"
        session_ids = self.redis_client.zrange(user_sessions_key, 0, -1)
        
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode('utf-8')
            self.destroy_session(session_id)
        
        # Clear the list
        self.redis_client.delete(user_sessions_key)
        
        logger.info(f"All sessions destroyed for user: {user_id}")
    
    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        user_sessions_key = f"user:sessions:{user_id}"
        session_ids = self.redis_client.zrange(user_sessions_key, 0, -1)
        
        sessions = []
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode('utf-8')
            
            session_data = self.redis_client.get(f"session:{session_id}")
            if session_data:
                sessions.append(json.loads(session_data))
        
        return sessions
    
    def _generate_fingerprint(
        self,
        ip_address: str,
        user_agent: str,
        device_id: Optional[str] = None
    ) -> str:
        """Generate session fingerprint"""
        components = [ip_address, user_agent]
        if device_id:
            components.append(device_id)
        
        fingerprint_data = '|'.join(components)
        return hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()
    
    def _enforce_session_limit(self, user_id: str):
        """Enforce concurrent session limit"""
        user_sessions_key = f"user:sessions:{user_id}"
        
        # Get session count
        session_count = self.redis_client.zcard(user_sessions_key)
        
        if session_count > self.concurrent_sessions:
            # Remove oldest sessions
            to_remove = session_count - self.concurrent_sessions
            oldest_sessions = self.redis_client.zrange(
                user_sessions_key, 0, to_remove - 1
            )
            
            for session_id in oldest_sessions:
                if isinstance(session_id, bytes):
                    session_id = session_id.decode('utf-8')
                self.destroy_session(session_id)


class IPManager:
    """IP address allowlisting/blocklisting and geolocation"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        geoip_db_path: Optional[str] = None,
        enable_geolocation: bool = False
    ):
        self.redis_client = redis_client
        self.enable_geolocation = enable_geolocation
        
        if enable_geolocation and geoip_db_path:
            try:
                self.geoip_reader = geoip2.database.Reader(geoip_db_path)
            except Exception as e:
                logger.warning(f"Failed to load GeoIP database: {str(e)}")
                self.geoip_reader = None
        else:
            self.geoip_reader = None
    
    def add_to_allowlist(
        self,
        ip_or_cidr: str,
        reason: str,
        expires_at: Optional[datetime] = None
    ):
        """Add IP or CIDR to allowlist"""
        # Validate IP/CIDR
        try:
            ipaddress.ip_network(ip_or_cidr)
        except ValueError:
            raise ValueError(f"Invalid IP or CIDR: {ip_or_cidr}")
        
        key = f"ip:allowlist:{ip_or_cidr}"
        data = {
            "reason": reason,
            "added_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None
        }
        
        if expires_at:
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            self.redis_client.setex(key, ttl, json.dumps(data))
        else:
            self.redis_client.set(key, json.dumps(data))
        
        logger.info(f"Added to allowlist: {ip_or_cidr}")
    
    def add_to_blocklist(
        self,
        ip_or_cidr: str,
        reason: str,
        expires_at: Optional[datetime] = None
    ):
        """Add IP or CIDR to blocklist"""
        # Validate IP/CIDR
        try:
            ipaddress.ip_network(ip_or_cidr)
        except ValueError:
            raise ValueError(f"Invalid IP or CIDR: {ip_or_cidr}")
        
        key = f"ip:blocklist:{ip_or_cidr}"
        data = {
            "reason": reason,
            "added_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None
        }
        
        if expires_at:
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            self.redis_client.setex(key, ttl, json.dumps(data))
        else:
            self.redis_client.set(key, json.dumps(data))
        
        logger.info(f"Added to blocklist: {ip_or_cidr}")
    
    def is_allowed(self, ip_address: str) -> Tuple[bool, Optional[str]]:
        """Check if IP is allowed
        
        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check if IP is valid
        try:
            ip = ipaddress.ip_address(ip_address)
        except ValueError:
            return False, "Invalid IP address"
        
        # Check blocklist first
        blocked, block_reason = self._check_list(ip, "blocklist")
        if blocked:
            return False, block_reason
        
        # Check allowlist
        allowed, allow_reason = self._check_list(ip, "allowlist")
        if allowed:
            return True, allow_reason
        
        # Default: allow if not in any list
        return True, None
    
    def _check_list(self, ip: ipaddress.IPv4Address, list_type: str) -> Tuple[bool, Optional[str]]:
        """Check if IP is in specified list"""
        # Check exact match
        key = f"ip:{list_type}:{str(ip)}"
        data = self.redis_client.get(key)
        if data:
            info = json.loads(data)
            return True, info.get('reason')
        
        # Check CIDR ranges
        for key in self.redis_client.scan_iter(match=f"ip:{list_type}:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            ip_or_cidr = key_str.split(':')[-1]
            
            try:
                network = ipaddress.ip_network(ip_or_cidr)
                if ip in network:
                    data = self.redis_client.get(key)
                    if data:
                        info = json.loads(data)
                        return True, info.get('reason')
            except ValueError:
                continue
        
        return False, None
    
    def get_geolocation(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get geolocation for IP address"""
        if not self.geoip_reader:
            return None
        
        try:
            response = self.geoip_reader.city(ip_address)
            return {
                "country": response.country.name,
                "country_code": response.country.iso_code,
                "city": response.city.name,
                "region": response.subdivisions.most_specific.name if response.subdivisions else None,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "timezone": response.location.time_zone
            }
        except Exception as e:
            logger.debug(f"Geolocation lookup failed for {ip_address}: {str(e)}")
            return None
    
    def remove_from_allowlist(self, ip_or_cidr: str):
        """Remove IP or CIDR from allowlist"""
        key = f"ip:allowlist:{ip_or_cidr}"
        self.redis_client.delete(key)
        logger.info(f"Removed from allowlist: {ip_or_cidr}")
    
    def remove_from_blocklist(self, ip_or_cidr: str):
        """Remove IP or CIDR from blocklist"""
        key = f"ip:blocklist:{ip_or_cidr}"
        self.redis_client.delete(key)
        logger.info(f"Removed from blocklist: {ip_or_cidr}")


class ThreatDetector:
    """Basic threat detection and anomaly detection"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        ip_manager: IPManager,
        window_size: int = 300,  # 5 minutes
        thresholds: Optional[Dict[str, int]] = None
    ):
        self.redis_client = redis_client
        self.ip_manager = ip_manager
        self.window_size = window_size
        self.thresholds = thresholds or {
            "failed_logins": 5,
            "api_calls": 1000,
            "unique_endpoints": 50,
            "error_rate": 0.5,
            "suspicious_patterns": 3
        }
        
        # Pattern matchers for common attacks
        self.attack_patterns = {
            "sql_injection": re.compile(r"(union|select|insert|update|delete|drop|--|'|\")", re.I),
            "xss": re.compile(r"(<script|javascript:|onerror=|onload=)", re.I),
            "path_traversal": re.compile(r"(\.\./|\.\.\\|%2e%2e)", re.I),
            "command_injection": re.compile(r"(;|&&|\|\||`|\$\()", re.I)
        }
    
    def track_event(
        self,
        event_type: str,
        ip_address: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Track security event"""
        timestamp = datetime.utcnow()
        window_start = timestamp - timedelta(seconds=self.window_size)
        
        # Track by IP
        ip_key = f"threat:ip:{ip_address}:{event_type}"
        self.redis_client.zadd(
            ip_key,
            {f"{timestamp.isoformat()}:{json.dumps(metadata or {})}": timestamp.timestamp()}
        )
        
        # Remove old entries
        self.redis_client.zremrangebyscore(
            ip_key,
            0,
            window_start.timestamp()
        )
        
        # Set expiry
        self.redis_client.expire(ip_key, self.window_size * 2)
        
        # Track by user if provided
        if user_id:
            user_key = f"threat:user:{user_id}:{event_type}"
            self.redis_client.zadd(
                user_key,
                {f"{timestamp.isoformat()}:{json.dumps(metadata or {})}": timestamp.timestamp()}
            )
            self.redis_client.zremrangebyscore(
                user_key,
                0,
                window_start.timestamp()
            )
            self.redis_client.expire(user_key, self.window_size * 2)
    
    def check_threats(
        self,
        ip_address: str,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Check for threats from IP/user"""
        threats = []
        
        # Check failed login attempts
        failed_logins = self._count_events(ip_address, "failed_login", user_id)
        if failed_logins > self.thresholds["failed_logins"]:
            threats.append({
                "type": "brute_force",
                "severity": "high",
                "description": f"Excessive failed login attempts: {failed_logins}",
                "recommendation": "Block IP temporarily"
            })
        
        # Check API call rate
        api_calls = self._count_events(ip_address, "api_call", user_id)
        if api_calls > self.thresholds["api_calls"]:
            threats.append({
                "type": "api_abuse",
                "severity": "medium",
                "description": f"Excessive API calls: {api_calls}",
                "recommendation": "Apply rate limiting"
            })
        
        # Check endpoint variety (potential scanning)
        unique_endpoints = self._count_unique_endpoints(ip_address)
        if unique_endpoints > self.thresholds["unique_endpoints"]:
            threats.append({
                "type": "scanning",
                "severity": "medium",
                "description": f"Accessing many unique endpoints: {unique_endpoints}",
                "recommendation": "Monitor closely"
            })
        
        # Check error rate
        error_rate = self._calculate_error_rate(ip_address)
        if error_rate > self.thresholds["error_rate"]:
            threats.append({
                "type": "suspicious_errors",
                "severity": "low",
                "description": f"High error rate: {error_rate:.2%}",
                "recommendation": "Investigate requests"
            })
        
        # Check for attack patterns
        pattern_matches = self._count_events(ip_address, "attack_pattern", user_id)
        if pattern_matches > self.thresholds["suspicious_patterns"]:
            threats.append({
                "type": "attack_patterns",
                "severity": "critical",
                "description": f"Attack patterns detected: {pattern_matches}",
                "recommendation": "Block immediately"
            })
        
        # Auto-block if critical threats
        if any(t["severity"] == "critical" for t in threats):
            self.ip_manager.add_to_blocklist(
                ip_address,
                f"Auto-blocked due to threats: {[t['type'] for t in threats]}",
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
        
        return threats
    
    def detect_attack_patterns(self, data: str, context: str = "unknown") -> List[str]:
        """Detect attack patterns in data"""
        detected_patterns = []
        
        for pattern_name, pattern in self.attack_patterns.items():
            if pattern.search(data):
                detected_patterns.append(pattern_name)
                
                # Track detection
                self.track_event(
                    "attack_pattern",
                    context,
                    metadata={
                        "pattern": pattern_name,
                        "sample": data[:100]
                    }
                )
        
        return detected_patterns
    
    def _count_events(
        self,
        ip_address: str,
        event_type: str,
        user_id: Optional[str] = None
    ) -> int:
        """Count events in current window"""
        count = 0
        
        # Count by IP
        ip_key = f"threat:ip:{ip_address}:{event_type}"
        count += self.redis_client.zcard(ip_key)
        
        # Count by user if provided
        if user_id:
            user_key = f"threat:user:{user_id}:{event_type}"
            count += self.redis_client.zcard(user_key)
        
        return count
    
    def _count_unique_endpoints(self, ip_address: str) -> int:
        """Count unique endpoints accessed"""
        key = f"threat:ip:{ip_address}:endpoints"
        return self.redis_client.scard(key)
    
    def _calculate_error_rate(self, ip_address: str) -> float:
        """Calculate error rate for IP"""
        total_calls = self._count_events(ip_address, "api_call")
        error_calls = self._count_events(ip_address, "api_error")
        
        if total_calls == 0:
            return 0.0
        
        return error_calls / total_calls