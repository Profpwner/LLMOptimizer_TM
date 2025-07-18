# Security Framework Documentation

## Overview

The LLMOptimizer Security Framework provides comprehensive security measures to protect the platform and meet SOC2 compliance requirements. It implements defense-in-depth strategies with multiple layers of security controls.

## Components

### 1. Authentication & Authorization

#### JWT Handler (`auth/jwt_handler.py`)
- **RS256 algorithm** with 4096-bit RSA keys
- **Refresh token support** with device tracking
- **Token blacklisting** for revocation
- **Automatic key rotation**
- **JWKS endpoint support** for external validation

```python
from shared.security import JWTHandler
import redis

redis_client = redis.Redis()
jwt_handler = JWTHandler(redis_client)

# Generate tokens
access_token, refresh_token, token_info = jwt_handler.generate_tokens(
    user_id="user123",
    claims={"roles": ["admin"]},
    device_id="device456"
)

# Verify token
payload = jwt_handler.verify_access_token(access_token)

# Refresh tokens
new_tokens = jwt_handler.refresh_access_token(refresh_token)

# Revoke all tokens for user
jwt_handler.revoke_tokens("user123")
```

#### RBAC Manager (`auth/rbac.py`)
- **Hierarchical roles** with inheritance
- **Fine-grained permissions**
- **Resource-based access control**
- **Dynamic permission evaluation**

```python
from shared.security import RBACManager, Permission

rbac = RBACManager(redis_client)

# Assign role
rbac.assign_role("user123", "developer", org_id="org456")

# Check permission
has_access = rbac.has_permission(
    "user123",
    Permission.CONTENT_CREATE,
    org_id="org456"
)

# Grant resource-specific access
rbac.grant_resource_access(
    user_id="user123",
    resource_type="content",
    resource_id="doc789",
    actions={"read", "update"},
    expires_at=datetime.utcnow() + timedelta(days=7)
)
```

### 2. Encryption

#### Field-level Encryption (`encryption/field_encryption.py`)
- **AES-256-GCM encryption**
- **Automatic key rotation**
- **Support for AWS KMS, HashiCorp Vault**
- **Field-level granularity**
- **Transparent encryption/decryption**

```python
from shared.security import FieldEncryption, KeyProvider

encryption = FieldEncryption(
    redis_client,
    key_provider=KeyProvider.AWS_KMS,
    kms_key_id="arn:aws:kms:us-east-1:123456789012:key/..."
)

# Encrypt sensitive data
encrypted = encryption.encrypt_field(
    data="sensitive information",
    field_name="ssn",
    context={"user_id": "user123"}
)

# Decrypt
decrypted = encryption.decrypt_field(encrypted)

# Encrypt multiple fields
encrypted_doc = encryption.encrypt_multiple_fields(
    data={"name": "John", "ssn": "123-45-6789", "email": "john@example.com"},
    fields_to_encrypt=["ssn", "email"]
)
```

### 3. Security Middleware

#### Security Headers (`middleware/security_headers.py`)
- **HSTS with preload**
- **CSP with nonce support**
- **XSS/Clickjacking protection**
- **CORS management**

```python
from shared.security import SecurityMiddlewareBuilder, SecurityPresets

# Custom configuration
security_middleware = SecurityMiddlewareBuilder() \
    .with_hsts(max_age=63072000) \
    .with_csp({
        "default-src": "'self'",
        "script-src": "'self' 'strict-dynamic'"
    }) \
    .with_cors(["https://app.example.com"]) \
    .build()

# Or use presets
api_security = SecurityPresets.api()
spa_security = SecurityPresets.spa()

# Apply to FastAPI
app.add_middleware(security_middleware)
```

#### Input Validation (`middleware/input_validation.py`)
- **SQL injection prevention**
- **XSS prevention**
- **Path traversal protection**
- **Data type validation**
- **File upload validation**

```python
from shared.security import InputValidator, ValidationLevel

validator = InputValidator(
    validation_level=ValidationLevel.STRICT,
    max_string_length=10000
)

# Validate string input
clean_input = validator.validate_string(
    user_input,
    min_length=3,
    max_length=100,
    pattern="alphanumeric"
)

# Validate email
email = validator.validate_email(email_input)

# Validate file upload
is_valid = validator.validate_file_upload(
    filename="document.pdf",
    content=file_content,
    allowed_extensions={'pdf', 'doc', 'docx'},
    max_size=10 * 1024 * 1024  # 10MB
)
```

#### Rate Limiting (`middleware/rate_limiter.py`)
- **Multiple strategies**: Fixed window, Sliding window, Token bucket, Leaky bucket
- **Distributed rate limiting**
- **Adaptive rate limiting**
- **IP and user-based limits**

```python
from shared.security import RateLimiter, RateLimitRule, RateLimitStrategy

rate_limiter = RateLimiter(redis_client)

# Add custom rule
rate_limiter.add_rule(RateLimitRule(
    name="api_standard",
    limit=100,
    window=60,  # 1 minute
    strategy=RateLimitStrategy.SLIDING_WINDOW,
    burst_limit=150
))

# Check rate limit
result = rate_limiter.check_rate_limit(
    key="192.168.1.1",
    rule_name="api_standard"
)

if not result.allowed:
    # Return 429 with retry_after
    pass
```

### 4. Audit Logging

#### Audit Logger (`audit/audit_logger.py`)
- **Structured logging** with correlation IDs
- **Tamper-proof with signatures**
- **Compression support**
- **7-year retention for SOC2**
- **Query and export capabilities**

```python
from shared.security import AuditLogger, AuditEventType

audit_logger = AuditLogger(redis_client)

# Log authentication
audit_logger.log_authentication(
    success=True,
    user_id="user123",
    user_email="user@example.com",
    ip_address="192.168.1.1"
)

# Log data access
audit_logger.log_data_access(
    action="read",
    resource_type="content",
    resource_id="doc789",
    user_id="user123"
)

# Log with correlation
with audit_logger.correlation_context() as correlation_id:
    # All logs within this context share correlation_id
    audit_logger.log_api_call(
        method="POST",
        path="/api/content",
        user_id="user123",
        status_code=200
    )

# Query logs
events = audit_logger.query_events(
    start_time=datetime.utcnow() - timedelta(days=7),
    event_types=[AuditEventType.AUTH_LOGIN_FAILURE],
    user_id="user123"
)
```

### 5. SOC2 Compliance

#### SOC2 Framework (`compliance/soc2_framework.py`)
- **All 5 trust principles**: Security, Availability, Processing Integrity, Confidentiality, Privacy
- **Automated compliance checks**
- **Incident tracking**
- **Report generation**

```python
from shared.security import SOC2Framework, TrustPrinciple

soc2 = SOC2Framework(redis_client, audit_logger)

# Run compliance assessment
results = await soc2.run_compliance_assessment(
    trust_principles=[TrustPrinciple.SECURITY, TrustPrinciple.PRIVACY]
)

# Record incident
incident_id = soc2.record_incident(
    incident_type="data_breach",
    severity="high",
    description="Unauthorized access attempt detected",
    affected_systems=["auth-service"],
    response_actions=["Access blocked", "Investigation started"]
)

# Generate compliance report
report = soc2.generate_compliance_report(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 3, 31)
)
```

### 6. Security Utilities

#### Password Validator (`utils/security_utils.py`)
- **Configurable password policies**
- **zxcvbn strength checking**
- **Password history**
- **Secure password generation**

```python
from shared.security import PasswordValidator, PasswordPolicy

policy = PasswordPolicy(
    min_length=12,
    require_uppercase=True,
    require_special=True,
    history_count=5,
    expiry_days=90
)

validator = PasswordValidator(redis_client, policy)

# Validate password
is_valid, errors = validator.validate_password(
    password="MySecureP@ssw0rd",
    user_info={"username": "john", "email": "john@example.com"},
    user_id="user123"
)

# Generate secure password
secure_password = validator.generate_secure_password(length=16)
```

#### Session Manager (`utils/security_utils.py`)
- **Secure session tokens**
- **Device fingerprinting**
- **Concurrent session limits**
- **Absolute timeout enforcement**

```python
from shared.security import SessionManager

session_manager = SessionManager(
    redis_client,
    session_timeout=3600,  # 1 hour
    concurrent_sessions=3
)

# Create session
session_id = session_manager.create_session(
    user_id="user123",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    device_id="device789"
)

# Validate session
session = session_manager.validate_session(
    session_id,
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0..."
)

# Destroy all sessions (logout everywhere)
session_manager.destroy_all_user_sessions("user123")
```

#### Threat Detector (`utils/security_utils.py`)
- **Brute force detection**
- **API abuse detection**
- **Attack pattern detection**
- **Automatic blocking**

```python
from shared.security import ThreatDetector, IPManager

ip_manager = IPManager(redis_client)
threat_detector = ThreatDetector(redis_client, ip_manager)

# Track failed login
threat_detector.track_event(
    event_type="failed_login",
    ip_address="192.168.1.1",
    user_id="user123"
)

# Check for threats
threats = threat_detector.check_threats("192.168.1.1")
# Returns: [{"type": "brute_force", "severity": "high", ...}]

# Detect attack patterns in input
patterns = threat_detector.detect_attack_patterns(
    user_input,
    context="api_request"
)
```

## Integration Examples

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from shared.security import (
    SecurityHeadersMiddleware,
    InputValidationMiddleware,
    RateLimitMiddleware,
    AuditLoggingMiddleware,
    JWTHandler,
    RBACManager
)

app = FastAPI()

# Apply security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditLoggingMiddleware)

# Dependency for authentication
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt_handler.verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401)
    return payload

# Dependency for authorization
def require_permission(permission: Permission):
    async def check_permission(user=Depends(get_current_user)):
        if not rbac.has_permission(user["sub"], permission):
            raise HTTPException(status_code=403)
        return user
    return check_permission

# Protected endpoint
@app.post("/api/content")
async def create_content(
    content: ContentModel,
    user=Depends(require_permission(Permission.CONTENT_CREATE))
):
    # Endpoint logic
    pass
```

### Environment Variables

```bash
# JWT Configuration
JWT_PRIVATE_KEY_PATH=/etc/llmoptimizer/keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/etc/llmoptimizer/keys/jwt_public.pem

# Encryption
MASTER_KEY_FILE=/etc/llmoptimizer/keys/master.key
AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/...

# Vault (if using HashiCorp Vault)
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Redis
REDIS_URL=redis://localhost:6379/0

# GeoIP Database (optional)
GEOIP_DB_PATH=/etc/llmoptimizer/GeoLite2-City.mmdb
```

## Security Best Practices

1. **Always use HTTPS** in production
2. **Enable all security headers** appropriate for your application
3. **Implement rate limiting** on all public endpoints
4. **Log all authentication attempts** and data access
5. **Encrypt sensitive data** at rest and in transit
6. **Regularly rotate keys** and credentials
7. **Monitor for threats** and anomalies
8. **Keep dependencies updated**
9. **Conduct regular security audits**
10. **Train team on security practices**

## Compliance Considerations

### SOC2 Type II
- Continuous monitoring enabled
- All controls implemented
- Audit trails maintained
- Regular assessments scheduled

### GDPR/CCPA
- Data encryption for PII
- Access controls implemented
- Audit logging for data access
- Data retention policies enforced

### OWASP Top 10
- Injection attacks prevented
- Authentication secure
- Sensitive data encrypted
- XXE attacks prevented
- Access control enforced
- Security misconfiguration prevented
- XSS prevented
- Deserialization attacks prevented
- Components monitored
- Logging and monitoring enabled

## Monitoring and Alerts

Configure alerts for:
- Failed authentication attempts > 5 in 5 minutes
- API rate limit violations
- Privilege escalation attempts
- Suspicious error patterns
- Configuration changes
- New device logins
- Compliance violations

## Testing

Run security tests:

```bash
# Unit tests
pytest tests/security/

# Integration tests
pytest tests/integration/security/

# Security scanning
bandit -r shared/security/
safety check

# SAST scanning
semgrep --config=auto shared/security/
```

## Support

For security issues or questions:
- Create a private security issue in the repository
- Contact the security team directly
- Never disclose vulnerabilities publicly

## License

This security framework is part of the LLMOptimizer project and follows the same license terms.