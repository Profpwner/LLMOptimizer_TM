"""Security Headers Middleware

Implements comprehensive security headers following OWASP guidelines
to protect against common web vulnerabilities.
"""

from typing import Dict, Optional, List, Callable
from datetime import datetime
import hashlib
import secrets
import json
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Middleware to add security headers to HTTP responses"""
    
    # Default security headers configuration
    DEFAULT_HEADERS = {
        # Prevent clickjacking attacks
        "X-Frame-Options": "DENY",
        
        # Prevent MIME type sniffing
        "X-Content-Type-Options": "nosniff",
        
        # Enable XSS protection in older browsers
        "X-XSS-Protection": "1; mode=block",
        
        # Control referrer information
        "Referrer-Policy": "strict-origin-when-cross-origin",
        
        # Permissions Policy (formerly Feature Policy)
        "Permissions-Policy": (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        ),
        
        # Prevent browsers from DNS prefetching
        "X-DNS-Prefetch-Control": "off",
        
        # Disable browser features that might be exploited
        "X-Permitted-Cross-Domain-Policies": "none",
        
        # Prevent IE from executing downloads in site context
        "X-Download-Options": "noopen"
    }
    
    def __init__(
        self,
        app=None,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = True,
        csp_directives: Optional[Dict[str, str]] = None,
        cors_origins: Optional[List[str]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        nonce_enabled: bool = True,
        report_uri: Optional[str] = None
    ):
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload
        self.csp_directives = self._build_csp_directives(csp_directives)
        self.cors_origins = cors_origins or []
        self.custom_headers = custom_headers or {}
        self.nonce_enabled = nonce_enabled
        self.report_uri = report_uri
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with application"""
        # For FastAPI
        if hasattr(app, 'middleware'):
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.requests import Request
            from starlette.responses import Response
            
            class SecurityHeadersMiddlewareWrapper(BaseHTTPMiddleware):
                def __init__(self, app, security_headers):
                    super().__init__(app)
                    self.security_headers = security_headers
                
                async def dispatch(self, request: Request, call_next):
                    # Generate nonce for this request
                    if self.security_headers.nonce_enabled:
                        request.state.csp_nonce = self.security_headers._generate_nonce()
                    
                    response = await call_next(request)
                    
                    # Add security headers
                    headers = self.security_headers.get_headers(request)
                    for header, value in headers.items():
                        response.headers[header] = value
                    
                    return response
            
            app.add_middleware(SecurityHeadersMiddlewareWrapper, security_headers=self)
        
        # For Flask
        elif hasattr(app, 'after_request'):
            @app.after_request
            def add_security_headers(response):
                headers = self.get_headers()
                for header, value in headers.items():
                    response.headers[header] = value
                return response
    
    def get_headers(self, request=None) -> Dict[str, str]:
        """Get all security headers"""
        headers = self.DEFAULT_HEADERS.copy()
        
        # Add HSTS header
        headers["Strict-Transport-Security"] = self._build_hsts_header()
        
        # Add CSP header
        csp_header = self._build_csp_header(request)
        if csp_header:
            headers["Content-Security-Policy"] = csp_header
            
            # Add Report-Only CSP for testing
            if self.report_uri:
                headers["Content-Security-Policy-Report-Only"] = csp_header
        
        # Add CORS headers if needed
        if request and self.cors_origins:
            cors_headers = self._build_cors_headers(request)
            headers.update(cors_headers)
        
        # Add custom headers
        headers.update(self.custom_headers)
        
        # Add security timestamp
        headers["X-Security-Timestamp"] = datetime.utcnow().isoformat()
        
        return headers
    
    def _build_hsts_header(self) -> str:
        """Build HSTS header value"""
        parts = [f"max-age={self.hsts_max_age}"]
        
        if self.hsts_include_subdomains:
            parts.append("includeSubDomains")
        
        if self.hsts_preload:
            parts.append("preload")
        
        return "; ".join(parts)
    
    def _build_csp_directives(self, custom_directives: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Build CSP directives"""
        # Default restrictive CSP
        directives = {
            "default-src": "'self'",
            "script-src": "'self' 'strict-dynamic'",
            "style-src": "'self' 'unsafe-inline'",  # Consider using nonces for styles too
            "img-src": "'self' data: https:",
            "font-src": "'self'",
            "connect-src": "'self'",
            "media-src": "'self'",
            "object-src": "'none'",
            "frame-src": "'none'",
            "base-uri": "'self'",
            "form-action": "'self'",
            "frame-ancestors": "'none'",
            "upgrade-insecure-requests": "",
            "block-all-mixed-content": ""
        }
        
        # Add custom directives
        if custom_directives:
            directives.update(custom_directives)
        
        # Add report URI if configured
        if self.report_uri:
            directives["report-uri"] = self.report_uri
            directives["report-to"] = "csp-endpoint"
        
        return directives
    
    def _build_csp_header(self, request=None) -> str:
        """Build CSP header value"""
        directives = self.csp_directives.copy()
        
        # Add nonce to script-src if enabled
        if self.nonce_enabled and request and hasattr(request, 'state') and hasattr(request.state, 'csp_nonce'):
            nonce = request.state.csp_nonce
            script_src = directives.get("script-src", "'self'")
            directives["script-src"] = f"{script_src} 'nonce-{nonce}'"
        
        # Build header string
        parts = []
        for directive, value in directives.items():
            if value:
                parts.append(f"{directive} {value}")
            else:
                parts.append(directive)
        
        return "; ".join(parts)
    
    def _build_cors_headers(self, request) -> Dict[str, str]:
        """Build CORS headers based on request origin"""
        headers = {}
        
        origin = request.headers.get("Origin")
        if not origin:
            return headers
        
        # Check if origin is allowed
        if origin in self.cors_origins or "*" in self.cors_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-Requested-With, X-CSRF-Token"
            )
            headers["Access-Control-Max-Age"] = "86400"  # 24 hours
            headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Page-Count"
        
        return headers
    
    def _generate_nonce(self) -> str:
        """Generate CSP nonce"""
        return base64.b64encode(secrets.token_bytes(16)).decode('ascii')
    
    def get_report_to_header(self) -> Dict[str, str]:
        """Get Report-To header for CSP reporting"""
        if not self.report_uri:
            return {}
        
        report_to = {
            "group": "csp-endpoint",
            "max_age": 10886400,  # 126 days
            "endpoints": [{"url": self.report_uri}]
        }
        
        return {"Report-To": json.dumps(report_to)}


class SecurityMiddlewareBuilder:
    """Builder for creating security middleware with custom configuration"""
    
    def __init__(self):
        self.config = {
            "hsts_max_age": 31536000,
            "hsts_include_subdomains": True,
            "hsts_preload": True,
            "csp_directives": {},
            "cors_origins": [],
            "custom_headers": {},
            "nonce_enabled": True,
            "report_uri": None
        }
    
    def with_hsts(
        self,
        max_age: int = 31536000,
        include_subdomains: bool = True,
        preload: bool = True
    ) -> 'SecurityMiddlewareBuilder':
        """Configure HSTS"""
        self.config.update({
            "hsts_max_age": max_age,
            "hsts_include_subdomains": include_subdomains,
            "hsts_preload": preload
        })
        return self
    
    def with_csp(self, directives: Dict[str, str]) -> 'SecurityMiddlewareBuilder':
        """Configure CSP directives"""
        self.config["csp_directives"] = directives
        return self
    
    def with_cors(self, origins: List[str]) -> 'SecurityMiddlewareBuilder':
        """Configure CORS origins"""
        self.config["cors_origins"] = origins
        return self
    
    def with_custom_headers(self, headers: Dict[str, str]) -> 'SecurityMiddlewareBuilder':
        """Add custom headers"""
        self.config["custom_headers"] = headers
        return self
    
    def with_nonce(self, enabled: bool = True) -> 'SecurityMiddlewareBuilder':
        """Enable/disable CSP nonce"""
        self.config["nonce_enabled"] = enabled
        return self
    
    def with_reporting(self, report_uri: str) -> 'SecurityMiddlewareBuilder':
        """Configure CSP reporting"""
        self.config["report_uri"] = report_uri
        return self
    
    def build(self) -> SecurityHeadersMiddleware:
        """Build security middleware"""
        return SecurityHeadersMiddleware(**self.config)


# Preset configurations
class SecurityPresets:
    """Common security header presets"""
    
    @staticmethod
    def strict() -> SecurityHeadersMiddleware:
        """Strict security configuration"""
        return SecurityMiddlewareBuilder() \
            .with_hsts(max_age=63072000, preload=True) \
            .with_csp({
                "default-src": "'none'",
                "script-src": "'self' 'strict-dynamic'",
                "style-src": "'self'",
                "img-src": "'self' data:",
                "font-src": "'self'",
                "connect-src": "'self'",
                "base-uri": "'none'",
                "form-action": "'self'",
                "frame-ancestors": "'none'"
            }) \
            .with_nonce(True) \
            .build()
    
    @staticmethod
    def api() -> SecurityHeadersMiddleware:
        """API-focused security configuration"""
        return SecurityMiddlewareBuilder() \
            .with_hsts() \
            .with_custom_headers({
                "X-API-Version": "1.0",
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }) \
            .build()
    
    @staticmethod
    def spa() -> SecurityHeadersMiddleware:
        """Single Page Application configuration"""
        return SecurityMiddlewareBuilder() \
            .with_hsts() \
            .with_csp({
                "default-src": "'self'",
                "script-src": "'self' 'unsafe-inline' 'unsafe-eval'",  # Required for some SPAs
                "style-src": "'self' 'unsafe-inline'",
                "img-src": "'self' data: https:",
                "font-src": "'self' data:",
                "connect-src": "'self' wss: https:",
                "frame-src": "'self'"
            }) \
            .with_cors(["https://app.example.com"]) \
            .build()


import base64