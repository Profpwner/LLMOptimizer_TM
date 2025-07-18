"""Security Module

Comprehensive security framework for LLMOptimizer including authentication,
encryption, compliance, and security utilities.
"""

from .auth.jwt_handler import JWTHandler
from .auth.rbac import RBACManager, Permission, Role
from .encryption.field_encryption import FieldEncryption, KeyProvider
from .middleware.security_headers import (
    SecurityHeadersMiddleware,
    SecurityMiddlewareBuilder,
    SecurityPresets
)
from .middleware.input_validation import (
    InputValidator,
    InputValidationMiddleware,
    ValidationLevel,
    ValidationRule
)
from .middleware.rate_limiter import (
    RateLimiter,
    RateLimitMiddleware,
    RateLimitStrategy,
    RateLimitRule,
    rate_limit
)
from .audit.audit_logger import (
    AuditLogger,
    AuditLoggingMiddleware,
    AuditEventType,
    AuditSeverity
)
from .compliance.soc2_framework import (
    SOC2Framework,
    TrustPrinciple,
    ControlCategory,
    ComplianceStatus
)
from .utils.security_utils import (
    PasswordValidator,
    PasswordPolicy,
    SessionManager,
    IPManager,
    ThreatDetector
)

__all__ = [
    # Auth
    'JWTHandler',
    'RBACManager',
    'Permission',
    'Role',
    
    # Encryption
    'FieldEncryption',
    'KeyProvider',
    
    # Middleware
    'SecurityHeadersMiddleware',
    'SecurityMiddlewareBuilder',
    'SecurityPresets',
    'InputValidator',
    'InputValidationMiddleware',
    'ValidationLevel',
    'ValidationRule',
    'RateLimiter',
    'RateLimitMiddleware',
    'RateLimitStrategy',
    'RateLimitRule',
    'rate_limit',
    
    # Audit
    'AuditLogger',
    'AuditLoggingMiddleware',
    'AuditEventType',
    'AuditSeverity',
    
    # Compliance
    'SOC2Framework',
    'TrustPrinciple',
    'ControlCategory',
    'ComplianceStatus',
    
    # Utils
    'PasswordValidator',
    'PasswordPolicy',
    'SessionManager',
    'IPManager',
    'ThreatDetector'
]

__version__ = "1.0.0"