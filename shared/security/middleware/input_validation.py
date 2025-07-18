"""Input Validation Middleware

Comprehensive input validation and sanitization to prevent injection attacks
and ensure data integrity following OWASP guidelines.
"""

import re
import json
import html
import urllib.parse
from typing import Any, Dict, List, Optional, Union, Callable, Set
from datetime import datetime
from decimal import Decimal
import ipaddress
import email_validator
import phonenumbers
import logging
from dataclasses import dataclass
from enum import Enum
import bleach
from pydantic import BaseModel, Field, validator, root_validator
import validators

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"      # Reject on any validation failure
    MODERATE = "moderate"  # Sanitize and warn on issues
    PERMISSIVE = "permissive"  # Sanitize without warnings


@dataclass
class ValidationRule:
    """Validation rule definition"""
    field_name: str
    rule_type: str
    parameters: Dict[str, Any]
    error_message: Optional[str] = None
    sanitize: bool = True


class InputValidator:
    """Comprehensive input validator with sanitization"""
    
    # Common regex patterns
    PATTERNS = {
        "alphanumeric": re.compile(r"^[a-zA-Z0-9]+$"),
        "alphanumeric_space": re.compile(r"^[a-zA-Z0-9\s]+$"),
        "username": re.compile(r"^[a-zA-Z0-9_-]{3,32}$"),
        "slug": re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
        "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I),
        "safe_string": re.compile(r"^[a-zA-Z0-9\s\-_.,:;!?()]+$"),
        "no_special_chars": re.compile(r"^[^<>&\"'`]+$"),
        "credit_card": re.compile(r"^[0-9]{13,19}$"),
        "ssn": re.compile(r"^\d{3}-?\d{2}-?\d{4}$"),
        "jwt": re.compile(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$")
    }
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)", re.I),
        re.compile(r"(--|#|\/\*|\*\/)", re.I),
        re.compile(r"(\bor\b\s*\d+\s*=\s*\d+)", re.I),
        re.compile(r"(\band\b\s*\d+\s*=\s*\d+)", re.I),
        re.compile(r"(';|';--|';#)", re.I),
        re.compile(r"(\bxp_\w+)", re.I),
        re.compile(r"(\bsp_\w+)", re.I)
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.I | re.S),
        re.compile(r"javascript:", re.I),
        re.compile(r"on\w+\s*=", re.I),
        re.compile(r"<iframe[^>]*>", re.I),
        re.compile(r"<object[^>]*>", re.I),
        re.compile(r"<embed[^>]*>", re.I),
        re.compile(r"<link[^>]*>", re.I),
        re.compile(r"<meta[^>]*>", re.I)
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        re.compile(r"\.\.\/"),
        re.compile(r"\.\.\\"),
        re.compile(r"%2e%2e%2f", re.I),
        re.compile(r"%2e%2e%5c", re.I),
        re.compile(r"\.\./"),
        re.compile(r"\.\.\\")
    ]
    
    def __init__(
        self,
        validation_level: ValidationLevel = ValidationLevel.STRICT,
        custom_patterns: Optional[Dict[str, re.Pattern]] = None,
        blocked_keywords: Optional[Set[str]] = None,
        max_string_length: int = 10000,
        allowed_html_tags: Optional[List[str]] = None,
        allowed_html_attributes: Optional[Dict[str, List[str]]] = None
    ):
        self.validation_level = validation_level
        self.custom_patterns = custom_patterns or {}
        self.blocked_keywords = blocked_keywords or set()
        self.max_string_length = max_string_length
        self.allowed_html_tags = allowed_html_tags or []
        self.allowed_html_attributes = allowed_html_attributes or {}
        
        # Merge custom patterns
        self.patterns = {**self.PATTERNS, **self.custom_patterns}
    
    def validate_string(
        self,
        value: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        allow_html: bool = False,
        strip_html: bool = True
    ) -> Union[str, None]:
        """Validate and sanitize string input"""
        if not isinstance(value, str):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Value must be a string")
            return None
        
        # Check length
        if len(value) > self.max_string_length:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"String exceeds maximum length of {self.max_string_length}")
            value = value[:self.max_string_length]
        
        if min_length and len(value) < min_length:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"String must be at least {min_length} characters")
            return None
        
        if max_length and len(value) > max_length:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"String must not exceed {max_length} characters")
            value = value[:max_length]
        
        # Check for injection patterns
        if self._contains_sql_injection(value):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Potential SQL injection detected")
            value = self._sanitize_sql(value)
        
        if not allow_html and self._contains_xss(value):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Potential XSS detected")
            value = self._sanitize_xss(value)
        
        # Apply pattern validation
        if pattern and pattern in self.patterns:
            if not self.patterns[pattern].match(value):
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError(f"Value does not match required pattern: {pattern}")
                return None
        
        # Strip or sanitize HTML
        if strip_html and not allow_html:
            value = self._strip_html(value)
        elif allow_html:
            value = self._sanitize_html(value)
        
        # Check blocked keywords
        if self._contains_blocked_keywords(value):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Value contains blocked keywords")
            value = self._remove_blocked_keywords(value)
        
        return value.strip()
    
    def validate_email(self, value: str) -> Union[str, None]:
        """Validate email address"""
        try:
            # Validate and normalize
            validation = email_validator.validate_email(value)
            return validation.email
        except email_validator.EmailNotValidError as e:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"Invalid email: {str(e)}")
            return None
    
    def validate_url(self, value: str, allowed_schemes: Optional[List[str]] = None) -> Union[str, None]:
        """Validate URL"""
        allowed_schemes = allowed_schemes or ["http", "https"]
        
        if not validators.url(value):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Invalid URL format")
            return None
        
        # Parse URL
        parsed = urllib.parse.urlparse(value)
        
        # Check scheme
        if parsed.scheme not in allowed_schemes:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"URL scheme must be one of: {allowed_schemes}")
            return None
        
        # Check for suspicious patterns
        if self._contains_path_traversal(value):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("URL contains path traversal patterns")
            return None
        
        return value
    
    def validate_phone(self, value: str, region: str = "US") -> Union[str, None]:
        """Validate phone number"""
        try:
            parsed = phonenumbers.parse(value, region)
            if not phonenumbers.is_valid_number(parsed):
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError("Invalid phone number")
                return None
            
            # Return formatted number
            return phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Invalid phone number format")
            return None
    
    def validate_ip_address(self, value: str, version: Optional[int] = None) -> Union[str, None]:
        """Validate IP address"""
        try:
            if version == 4:
                ipaddress.IPv4Address(value)
            elif version == 6:
                ipaddress.IPv6Address(value)
            else:
                # Try both
                try:
                    ipaddress.ip_address(value)
                except ValueError:
                    raise ValueError("Invalid IP address")
            
            return value
        except ValueError as e:
            if self.validation_level == ValidationLevel.STRICT:
                raise e
            return None
    
    def validate_number(
        self,
        value: Any,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        decimal_places: Optional[int] = None
    ) -> Union[float, Decimal, None]:
        """Validate numeric input"""
        try:
            if decimal_places is not None:
                num = Decimal(str(value))
                # Check decimal places
                if num.as_tuple().exponent < -decimal_places:
                    if self.validation_level == ValidationLevel.STRICT:
                        raise ValueError(f"Too many decimal places (max: {decimal_places})")
                    # Round to specified decimal places
                    num = round(num, decimal_places)
            else:
                num = float(value)
            
            # Check range
            if min_value is not None and num < min_value:
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError(f"Value must be at least {min_value}")
                return None
            
            if max_value is not None and num > max_value:
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError(f"Value must not exceed {max_value}")
                return None
            
            return num
        except (ValueError, TypeError):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Invalid numeric value")
            return None
    
    def validate_date(
        self,
        value: str,
        format: str = "%Y-%m-%d",
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None
    ) -> Union[datetime, None]:
        """Validate date input"""
        try:
            date = datetime.strptime(value, format)
            
            # Check range
            if min_date and date < min_date:
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError(f"Date must be after {min_date}")
                return None
            
            if max_date and date > max_date:
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError(f"Date must be before {max_date}")
                return None
            
            return date
        except ValueError:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"Invalid date format (expected: {format})")
            return None
    
    def validate_json(self, value: str, schema: Optional[Dict] = None) -> Union[Dict, List, None]:
        """Validate JSON input"""
        try:
            data = json.loads(value)
            
            # Validate against schema if provided
            if schema:
                import jsonschema
                jsonschema.validate(data, schema)
            
            return data
        except json.JSONDecodeError:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Invalid JSON format")
            return None
        except jsonschema.ValidationError as e:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"JSON schema validation failed: {str(e)}")
            return None
    
    def validate_file_upload(
        self,
        filename: str,
        content: bytes,
        allowed_extensions: Optional[Set[str]] = None,
        max_size: Optional[int] = None,
        check_content: bool = True
    ) -> bool:
        """Validate file upload"""
        # Default allowed extensions
        if allowed_extensions is None:
            allowed_extensions = {
                'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx',
                'xls', 'xlsx', 'txt', 'csv', 'zip'
            }
        
        # Check filename
        filename = self.validate_filename(filename)
        if not filename:
            return False
        
        # Check extension
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext not in allowed_extensions:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"File type not allowed: {ext}")
            return False
        
        # Check size
        if max_size and len(content) > max_size:
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError(f"File size exceeds maximum of {max_size} bytes")
            return False
        
        # Check content type
        if check_content:
            import magic
            mime = magic.from_buffer(content[:1024], mime=True)
            
            # Map extensions to expected MIME types
            mime_mapping = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'pdf': 'application/pdf',
                'zip': 'application/zip'
            }
            
            expected_mime = mime_mapping.get(ext)
            if expected_mime and mime != expected_mime:
                if self.validation_level == ValidationLevel.STRICT:
                    raise ValueError(f"File content does not match extension")
                return False
        
        return True
    
    def validate_filename(self, filename: str) -> Union[str, None]:
        """Validate and sanitize filename"""
        if not filename:
            return None
        
        # Remove path components
        filename = os.path.basename(filename)
        
        # Check for path traversal
        if self._contains_path_traversal(filename):
            if self.validation_level == ValidationLevel.STRICT:
                raise ValueError("Filename contains path traversal patterns")
            return None
        
        # Sanitize filename
        # Remove any non-alphanumeric characters except .-_
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
        
        return filename
    
    def _contains_sql_injection(self, value: str) -> bool:
        """Check for SQL injection patterns"""
        for pattern in self.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                logger.warning(f"Potential SQL injection detected: {value[:50]}...")
                return True
        return False
    
    def _contains_xss(self, value: str) -> bool:
        """Check for XSS patterns"""
        for pattern in self.XSS_PATTERNS:
            if pattern.search(value):
                logger.warning(f"Potential XSS detected: {value[:50]}...")
                return True
        return False
    
    def _contains_path_traversal(self, value: str) -> bool:
        """Check for path traversal patterns"""
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if pattern.search(value):
                logger.warning(f"Potential path traversal detected: {value[:50]}...")
                return True
        return False
    
    def _contains_blocked_keywords(self, value: str) -> bool:
        """Check for blocked keywords"""
        value_lower = value.lower()
        for keyword in self.blocked_keywords:
            if keyword.lower() in value_lower:
                return True
        return False
    
    def _sanitize_sql(self, value: str) -> str:
        """Sanitize SQL injection attempts"""
        # Remove SQL keywords and operators
        for pattern in self.SQL_INJECTION_PATTERNS:
            value = pattern.sub('', value)
        return value
    
    def _sanitize_xss(self, value: str) -> str:
        """Sanitize XSS attempts"""
        # HTML encode
        return html.escape(value)
    
    def _strip_html(self, value: str) -> str:
        """Strip all HTML tags"""
        return bleach.clean(value, tags=[], strip=True)
    
    def _sanitize_html(self, value: str) -> str:
        """Sanitize HTML content"""
        return bleach.clean(
            value,
            tags=self.allowed_html_tags,
            attributes=self.allowed_html_attributes,
            strip=True
        )
    
    def _remove_blocked_keywords(self, value: str) -> str:
        """Remove blocked keywords"""
        for keyword in self.blocked_keywords:
            value = re.sub(
                re.escape(keyword),
                '*' * len(keyword),
                value,
                flags=re.IGNORECASE
            )
        return value


class InputValidationMiddleware:
    """Middleware for request input validation"""
    
    def __init__(
        self,
        app=None,
        validator: Optional[InputValidator] = None,
        validation_rules: Optional[Dict[str, List[ValidationRule]]] = None,
        exclude_paths: Optional[List[str]] = None
    ):
        self.validator = validator or InputValidator()
        self.validation_rules = validation_rules or {}
        self.exclude_paths = exclude_paths or []
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with application"""
        # For FastAPI
        if hasattr(app, 'middleware'):
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.requests import Request
            from starlette.responses import JSONResponse
            
            class ValidationMiddlewareWrapper(BaseHTTPMiddleware):
                def __init__(self, app, validation_middleware):
                    super().__init__(app)
                    self.validation_middleware = validation_middleware
                
                async def dispatch(self, request: Request, call_next):
                    # Skip validation for excluded paths
                    if request.url.path in self.validation_middleware.exclude_paths:
                        return await call_next(request)
                    
                    # Validate request
                    try:
                        await self.validation_middleware.validate_request(request)
                    except ValueError as e:
                        return JSONResponse(
                            status_code=400,
                            content={"error": str(e)}
                        )
                    
                    return await call_next(request)
            
            app.add_middleware(ValidationMiddlewareWrapper, validation_middleware=self)
    
    async def validate_request(self, request):
        """Validate incoming request"""
        # Get validation rules for endpoint
        path = request.url.path
        method = request.method
        
        rule_key = f"{method}:{path}"
        rules = self.validation_rules.get(rule_key, [])
        
        if not rules:
            return
        
        # Get request data
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
            except:
                body = {}
        else:
            body = dict(request.query_params)
        
        # Apply validation rules
        for rule in rules:
            field_value = body.get(rule.field_name)
            
            if field_value is None and rule.rule_type != "required":
                continue
            
            # Apply validation based on rule type
            if rule.rule_type == "required" and field_value is None:
                raise ValueError(f"{rule.field_name} is required")
            
            elif rule.rule_type == "string":
                validated = self.validator.validate_string(
                    field_value,
                    **rule.parameters
                )
                if validated is None:
                    raise ValueError(rule.error_message or f"Invalid {rule.field_name}")
                body[rule.field_name] = validated
            
            elif rule.rule_type == "email":
                validated = self.validator.validate_email(field_value)
                if validated is None:
                    raise ValueError(rule.error_message or f"Invalid email: {rule.field_name}")
                body[rule.field_name] = validated
            
            elif rule.rule_type == "number":
                validated = self.validator.validate_number(
                    field_value,
                    **rule.parameters
                )
                if validated is None:
                    raise ValueError(rule.error_message or f"Invalid number: {rule.field_name}")
                body[rule.field_name] = validated
        
        # Update request with sanitized data
        request.state.validated_data = body


import os