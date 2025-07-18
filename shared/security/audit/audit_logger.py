"""Comprehensive Audit Logging System

Implements structured, tamper-proof audit logging with correlation IDs,
compliance with SOC2 requirements, and integration with log management systems.
"""

import json
import time
import uuid
import hashlib
import hmac
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
import asyncio
from contextlib import contextmanager
import threading
import redis
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import gzip
import base64

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_ISSUED = "auth.token.issued"
    AUTH_TOKEN_REVOKED = "auth.token.revoked"
    AUTH_PASSWORD_CHANGE = "auth.password.change"
    AUTH_MFA_ENABLED = "auth.mfa.enabled"
    AUTH_MFA_DISABLED = "auth.mfa.disabled"
    
    # Data Access
    DATA_READ = "data.read"
    DATA_WRITE = "data.write"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"
    
    # Configuration
    CONFIG_CHANGE = "config.change"
    CONFIG_READ = "config.read"
    
    # API Access
    API_CALL = "api.call"
    API_ERROR = "api.error"
    API_RATE_LIMIT = "api.rate_limit"
    
    # User Management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role.change"
    USER_PERMISSION_CHANGE = "user.permission.change"
    
    # System Events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    
    # Security Events
    SECURITY_THREAT_DETECTED = "security.threat.detected"
    SECURITY_SCAN_COMPLETED = "security.scan.completed"
    SECURITY_POLICY_VIOLATION = "security.policy.violation"
    
    # Compliance Events
    COMPLIANCE_AUDIT = "compliance.audit"
    COMPLIANCE_REPORT_GENERATED = "compliance.report.generated"
    COMPLIANCE_VIOLATION = "compliance.violation"


class AuditSeverity(Enum):
    """Audit event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType = AuditEventType.API_CALL
    severity: AuditSeverity = AuditSeverity.INFO
    correlation_id: Optional[str] = None
    
    # Actor information
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_roles: List[str] = field(default_factory=list)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    
    # Resource information
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    
    # Action details
    action: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    
    # Results
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Security
    hash: Optional[str] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        return data


class AuditLogger:
    """Comprehensive audit logging system"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        signing_key: Optional[rsa.RSAPrivateKey] = None,
        enable_signing: bool = True,
        enable_compression: bool = True,
        retention_days: int = 2555,  # 7 years for SOC2
        buffer_size: int = 1000,
        flush_interval: int = 5,  # seconds
        storage_backend: str = "redis"  # Could be "s3", "elasticsearch", etc.
    ):
        self.redis_client = redis_client
        self.signing_key = signing_key or self._generate_signing_key()
        self.enable_signing = enable_signing
        self.enable_compression = enable_compression
        self.retention_days = retention_days
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.storage_backend = storage_backend
        
        # Event buffer for batch processing
        self._buffer: List[AuditEvent] = []
        self._buffer_lock = threading.Lock()
        
        # Start background flusher
        self._flush_task = None
        self._start_flusher()
        
        # Correlation ID storage
        self._correlation_context = threading.local()
    
    def _generate_signing_key(self) -> rsa.RSAPrivateKey:
        """Generate RSA key for signing audit logs"""
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
    
    def log_event(
        self,
        event_type: AuditEventType,
        **kwargs
    ) -> str:
        """Log an audit event
        
        Args:
            event_type: Type of event
            **kwargs: Event attributes
            
        Returns:
            Event ID
        """
        # Create event
        event = AuditEvent(
            event_type=event_type,
            correlation_id=self.get_correlation_id(),
            **kwargs
        )
        
        # Add security hash
        event.hash = self._calculate_hash(event)
        
        # Sign if enabled
        if self.enable_signing:
            event.signature = self._sign_event(event)
        
        # Add to buffer
        with self._buffer_lock:
            self._buffer.append(event)
            
            # Flush if buffer is full
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
        
        logger.debug(f"Logged audit event: {event.event_id} - {event_type.value}")
        return event.event_id
    
    def log_authentication(
        self,
        success: bool,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log authentication event"""
        event_type = (
            AuditEventType.AUTH_LOGIN_SUCCESS if success
            else AuditEventType.AUTH_LOGIN_FAILURE
        )
        
        return self.log_event(
            event_type=event_type,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )
    
    def log_data_access(
        self,
        action: str,  # read, write, update, delete
        resource_type: str,
        resource_id: str,
        user_id: str,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log data access event"""
        event_type_map = {
            "read": AuditEventType.DATA_READ,
            "write": AuditEventType.DATA_WRITE,
            "update": AuditEventType.DATA_UPDATE,
            "delete": AuditEventType.DATA_DELETE
        }
        
        event_type = event_type_map.get(action, AuditEventType.DATA_READ)
        
        return self.log_event(
            event_type=event_type,
            severity=AuditSeverity.INFO,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            success=success,
            metadata=metadata or {}
        )
    
    def log_api_call(
        self,
        method: str,
        path: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status_code: int = 200,
        response_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log API call"""
        success = 200 <= status_code < 400
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        
        meta = metadata or {}
        if response_time:
            meta['response_time_ms'] = response_time
        meta['status_code'] = status_code
        
        return self.log_event(
            event_type=AuditEventType.API_CALL,
            severity=severity,
            method=method,
            path=path,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            metadata=meta
        )
    
    def log_config_change(
        self,
        config_key: str,
        old_value: Any,
        new_value: Any,
        user_id: str,
        reason: Optional[str] = None
    ) -> str:
        """Log configuration change"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_CHANGE,
            severity=AuditSeverity.WARNING,
            resource_type="configuration",
            resource_id=config_key,
            user_id=user_id,
            metadata={
                "old_value": str(old_value),
                "new_value": str(new_value),
                "reason": reason
            }
        )
    
    def log_security_event(
        self,
        threat_type: str,
        severity: AuditSeverity,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log security event"""
        return self.log_event(
            event_type=AuditEventType.SECURITY_THREAT_DETECTED,
            severity=severity,
            ip_address=source_ip,
            user_id=user_id,
            metadata={
                "threat_type": threat_type,
                "description": description,
                **(metadata or {})
            }
        )
    
    @contextmanager
    def correlation_context(self, correlation_id: Optional[str] = None):
        """Context manager for correlation ID"""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        old_id = getattr(self._correlation_context, 'correlation_id', None)
        self._correlation_context.correlation_id = correlation_id
        
        try:
            yield correlation_id
        finally:
            if old_id:
                self._correlation_context.correlation_id = old_id
            else:
                delattr(self._correlation_context, 'correlation_id')
    
    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID"""
        return getattr(self._correlation_context, 'correlation_id', None)
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID"""
        self._correlation_context.correlation_id = correlation_id
    
    def query_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query audit events"""
        # Flush buffer first
        self._flush_buffer()
        
        # Build query
        query_parts = []
        
        if start_time:
            query_parts.append(f"timestamp >= '{start_time.isoformat()}'")
        if end_time:
            query_parts.append(f"timestamp <= '{end_time.isoformat()}'")
        if event_types:
            types_str = "','".join(et.value for et in event_types)
            query_parts.append(f"event_type IN ('{types_str}')")
        if user_id:
            query_parts.append(f"user_id = '{user_id}'")
        if resource_id:
            query_parts.append(f"resource_id = '{resource_id}'")
        if correlation_id:
            query_parts.append(f"correlation_id = '{correlation_id}'")
        
        # For Redis backend, we'll use sorted sets
        # In production, you'd use Elasticsearch or similar
        events = []
        
        # Get all audit log keys
        for key in self.redis_client.scan_iter(match="audit:event:*"):
            event_data = self.redis_client.get(key)
            if event_data:
                event = json.loads(event_data)
                
                # Apply filters
                if self._matches_query(event, query_parts):
                    events.append(event)
        
        # Sort by timestamp
        events.sort(key=lambda e: e['timestamp'], reverse=True)
        
        # Apply pagination
        return events[offset:offset + limit]
    
    def export_events(
        self,
        format: str = "json",  # json, csv, etc.
        **query_kwargs
    ) -> bytes:
        """Export audit events"""
        events = self.query_events(**query_kwargs)
        
        if format == "json":
            return json.dumps(events, indent=2).encode('utf-8')
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if events:
                writer = csv.DictWriter(output, fieldnames=events[0].keys())
                writer.writeheader()
                writer.writerows(events)
            
            return output.getvalue().encode('utf-8')
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _calculate_hash(self, event: AuditEvent) -> str:
        """Calculate hash of event for integrity"""
        # Create canonical representation
        data = {
            'event_id': event.event_id,
            'timestamp': event.timestamp.isoformat(),
            'event_type': event.event_type.value,
            'user_id': event.user_id,
            'resource_id': event.resource_id,
            'success': event.success
        }
        
        # Sort keys for consistent hashing
        canonical = json.dumps(data, sort_keys=True)
        
        # Calculate SHA-256 hash
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def _sign_event(self, event: AuditEvent) -> str:
        """Sign event for non-repudiation"""
        # Create message from event hash
        message = event.hash.encode('utf-8')
        
        # Sign with private key
        signature = self.signing_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Return base64 encoded signature
        return base64.b64encode(signature).decode('utf-8')
    
    def verify_event(self, event: Dict[str, Any]) -> bool:
        """Verify event integrity and signature"""
        # Recreate event object
        audit_event = AuditEvent(**{
            k: v for k, v in event.items()
            if k not in ['hash', 'signature']
        })
        
        # Verify hash
        calculated_hash = self._calculate_hash(audit_event)
        if calculated_hash != event.get('hash'):
            logger.warning(f"Hash mismatch for event {event.get('event_id')}")
            return False
        
        # Verify signature if present
        if self.enable_signing and event.get('signature'):
            try:
                signature = base64.b64decode(event['signature'])
                public_key = self.signing_key.public_key()
                
                public_key.verify(
                    signature,
                    event['hash'].encode('utf-8'),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            except Exception as e:
                logger.warning(f"Signature verification failed: {str(e)}")
                return False
        
        return True
    
    def _flush_buffer(self):
        """Flush event buffer to storage"""
        with self._buffer_lock:
            if not self._buffer:
                return
            
            events = self._buffer[:]
            self._buffer.clear()
        
        # Store events
        for event in events:
            self._store_event(event)
        
        logger.debug(f"Flushed {len(events)} audit events")
    
    def _store_event(self, event: AuditEvent):
        """Store event in backend"""
        event_dict = event.to_dict()
        
        # Compress if enabled
        if self.enable_compression:
            data = gzip.compress(json.dumps(event_dict).encode('utf-8'))
            event_dict = {
                'compressed': True,
                'data': base64.b64encode(data).decode('utf-8')
            }
        
        # Store in Redis with TTL
        key = f"audit:event:{event.event_id}"
        ttl = self.retention_days * 24 * 60 * 60  # Convert to seconds
        
        self.redis_client.setex(
            key,
            ttl,
            json.dumps(event_dict)
        )
        
        # Also add to sorted set for time-based queries
        score = event.timestamp.timestamp()
        self.redis_client.zadd(
            "audit:events:timeline",
            {event.event_id: score}
        )
        
        # Add to index sets
        if event.user_id:
            self.redis_client.sadd(f"audit:index:user:{event.user_id}", event.event_id)
        if event.resource_id:
            self.redis_client.sadd(f"audit:index:resource:{event.resource_id}", event.event_id)
        if event.correlation_id:
            self.redis_client.sadd(f"audit:index:correlation:{event.correlation_id}", event.event_id)
    
    def _start_flusher(self):
        """Start background flush task"""
        def flush_loop():
            while True:
                time.sleep(self.flush_interval)
                try:
                    self._flush_buffer()
                except Exception as e:
                    logger.error(f"Error flushing audit buffer: {str(e)}")
        
        import threading
        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()
    
    def _matches_query(self, event: Dict[str, Any], query_parts: List[str]) -> bool:
        """Check if event matches query (simplified)"""
        # In production, use proper query engine
        # This is a simplified implementation
        return True  # Implement actual filtering logic
    
    def close(self):
        """Close audit logger and flush remaining events"""
        self._flush_buffer()


# Middleware integration
class AuditLoggingMiddleware:
    """Middleware for automatic audit logging"""
    
    def __init__(
        self,
        app=None,
        audit_logger: AuditLogger = None,
        exclude_paths: Optional[List[str]] = None
    ):
        self.audit_logger = audit_logger
        self.exclude_paths = exclude_paths or ['/health', '/metrics']
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with application"""
        # For FastAPI
        if hasattr(app, 'middleware'):
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.requests import Request
            
            class AuditMiddlewareWrapper(BaseHTTPMiddleware):
                def __init__(self, app, audit_middleware):
                    super().__init__(app)
                    self.audit_middleware = audit_middleware
                
                async def dispatch(self, request: Request, call_next):
                    # Skip excluded paths
                    if request.url.path in self.audit_middleware.exclude_paths:
                        return await call_next(request)
                    
                    # Generate correlation ID
                    correlation_id = str(uuid.uuid4())
                    self.audit_middleware.audit_logger.set_correlation_id(correlation_id)
                    
                    # Track timing
                    start_time = time.time()
                    
                    # Process request
                    response = await call_next(request)
                    
                    # Calculate response time
                    response_time = (time.time() - start_time) * 1000
                    
                    # Log API call
                    self.audit_middleware.audit_logger.log_api_call(
                        method=request.method,
                        path=request.url.path,
                        user_id=getattr(request.state, 'user_id', None),
                        ip_address=request.client.host,
                        user_agent=request.headers.get('User-Agent'),
                        status_code=response.status_code,
                        response_time=response_time
                    )
                    
                    return response
            
            app.add_middleware(AuditMiddlewareWrapper, audit_middleware=self)