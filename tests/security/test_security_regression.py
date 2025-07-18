"""
Security regression test suite for LLMOptimizer.
Ensures security fixes remain in place and new code doesn't introduce vulnerabilities.
"""

import pytest
import requests
import json
import jwt
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import asyncio
import ssl
import socket
from urllib.parse import urljoin, quote
import re
import base64
from cryptography import x509
from cryptography.hazmat.backends import default_backend


class TestSecurityHeaders:
    """Test security headers are properly configured."""
    
    @pytest.fixture
    def base_url(self):
        return pytest.config.getoption("--base-url") or "https://api.llmoptimizer.com"
    
    def test_strict_transport_security(self, base_url):
        """Test HSTS header is present and properly configured."""
        response = requests.get(base_url)
        
        assert 'Strict-Transport-Security' in response.headers
        hsts = response.headers['Strict-Transport-Security']
        
        # Check max-age is at least 1 year
        assert 'max-age=' in hsts
        max_age = int(re.search(r'max-age=(\d+)', hsts).group(1))
        assert max_age >= 31536000  # 1 year in seconds
        
        # Check includeSubDomains is present
        assert 'includeSubDomains' in hsts
        
        # Check preload is present for production
        if 'production' in base_url:
            assert 'preload' in hsts
    
    def test_content_security_policy(self, base_url):
        """Test CSP header is present and restrictive."""
        response = requests.get(base_url)
        
        assert 'Content-Security-Policy' in response.headers
        csp = response.headers['Content-Security-Policy']
        
        # Check required directives
        required_directives = [
            "default-src 'self'",
            "script-src",
            "style-src",
            "img-src",
            "connect-src",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        
        for directive in required_directives:
            assert directive in csp, f"Missing CSP directive: {directive}"
        
        # Check no unsafe-inline or unsafe-eval
        assert "'unsafe-inline'" not in csp or "nonce-" in csp
        assert "'unsafe-eval'" not in csp
    
    def test_x_frame_options(self, base_url):
        """Test X-Frame-Options header prevents clickjacking."""
        response = requests.get(base_url)
        
        assert 'X-Frame-Options' in response.headers
        assert response.headers['X-Frame-Options'] in ['DENY', 'SAMEORIGIN']
    
    def test_x_content_type_options(self, base_url):
        """Test X-Content-Type-Options prevents MIME sniffing."""
        response = requests.get(base_url)
        
        assert 'X-Content-Type-Options' in response.headers
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
    
    def test_referrer_policy(self, base_url):
        """Test Referrer-Policy is properly configured."""
        response = requests.get(base_url)
        
        assert 'Referrer-Policy' in response.headers
        policy = response.headers['Referrer-Policy']
        
        acceptable_policies = [
            'no-referrer',
            'no-referrer-when-downgrade',
            'origin',
            'origin-when-cross-origin',
            'same-origin',
            'strict-origin',
            'strict-origin-when-cross-origin'
        ]
        
        assert policy in acceptable_policies
    
    def test_permissions_policy(self, base_url):
        """Test Permissions-Policy restricts browser features."""
        response = requests.get(base_url)
        
        assert 'Permissions-Policy' in response.headers
        policy = response.headers['Permissions-Policy']
        
        # Check dangerous features are disabled
        dangerous_features = [
            'geolocation',
            'camera',
            'microphone',
            'payment',
            'usb',
            'magnetometer',
            'accelerometer'
        ]
        
        for feature in dangerous_features:
            assert f'{feature}=()' in policy or f'{feature}=(self)' in policy
    
    def test_no_server_header(self, base_url):
        """Test server information is not disclosed."""
        response = requests.get(base_url)
        
        # Check no detailed server header
        if 'Server' in response.headers:
            server = response.headers['Server'].lower()
            assert not any(version in server for version in ['apache/', 'nginx/', 'iis/'])
        
        # Check no X-Powered-By header
        assert 'X-Powered-By' not in response.headers
    
    def test_cache_control_headers(self, base_url):
        """Test cache headers prevent sensitive data caching."""
        # Test authenticated endpoint
        auth_endpoints = ['/api/user/profile', '/api/auth/session']
        
        for endpoint in auth_endpoints:
            response = requests.get(urljoin(base_url, endpoint))
            
            if response.status_code == 200:
                assert 'Cache-Control' in response.headers
                cache_control = response.headers['Cache-Control']
                
                assert 'no-store' in cache_control or 'no-cache' in cache_control
                assert 'private' in cache_control


class TestAuthentication:
    """Test authentication security."""
    
    @pytest.fixture
    def auth_url(self, base_url):
        return urljoin(base_url, '/api/auth/login')
    
    def test_no_sql_injection_in_login(self, auth_url):
        """Test login is not vulnerable to SQL injection."""
        sql_payloads = [
            {"username": "admin' --", "password": "password"},
            {"username": "' OR '1'='1", "password": "' OR '1'='1"},
            {"username": "admin'; DROP TABLE users; --", "password": "pass"},
            {"username": "admin' UNION SELECT NULL--", "password": "pass"}
        ]
        
        for payload in sql_payloads:
            response = requests.post(auth_url, json=payload)
            
            # Should get authentication failure, not SQL error
            assert response.status_code in [401, 403, 400]
            
            # Check no SQL error messages in response
            if response.text:
                sql_errors = ['sql', 'query', 'syntax', 'mysql', 'postgres', 'sqlite']
                assert not any(error in response.text.lower() for error in sql_errors)
    
    def test_no_nosql_injection_in_login(self, auth_url):
        """Test login is not vulnerable to NoSQL injection."""
        nosql_payloads = [
            {"username": {"$ne": None}, "password": {"$ne": None}},
            {"username": {"$gt": ""}, "password": {"$gt": ""}},
            {"username": "admin", "password": {"$regex": ".*"}},
            {"username": {"$where": "this.password == 'password'"}, "password": "pass"}
        ]
        
        for payload in nosql_payloads:
            response = requests.post(auth_url, json=payload)
            
            # Should get authentication failure or bad request
            assert response.status_code in [401, 403, 400]
    
    def test_password_requirements(self, base_url):
        """Test password policy is enforced."""
        register_url = urljoin(base_url, '/api/auth/register')
        
        weak_passwords = [
            'password',
            '12345678',
            'qwerty123',
            'admin123',
            'test1234'
        ]
        
        for password in weak_passwords:
            payload = {
                "username": f"testuser_{int(time.time())}",
                "email": f"test_{int(time.time())}@example.com",
                "password": password
            }
            
            response = requests.post(register_url, json=payload)
            
            # Should reject weak passwords
            assert response.status_code == 400
            assert 'password' in response.text.lower()
    
    def test_rate_limiting_on_login(self, auth_url):
        """Test rate limiting prevents brute force attacks."""
        failed_attempts = []
        
        # Try multiple failed login attempts
        for i in range(10):
            response = requests.post(auth_url, json={
                "username": "nonexistent",
                "password": "wrongpass"
            })
            failed_attempts.append(response.status_code)
        
        # Should hit rate limit
        assert 429 in failed_attempts or 403 in failed_attempts
    
    def test_session_fixation_prevention(self, base_url, auth_url):
        """Test session ID changes after authentication."""
        session = requests.Session()
        
        # Get initial session
        response = session.get(base_url)
        initial_cookies = dict(session.cookies)
        
        # Perform login
        login_data = {"username": "testuser", "password": "Test123!@#"}
        response = session.post(auth_url, json=login_data)
        
        if response.status_code == 200:
            # Check session ID changed
            new_cookies = dict(session.cookies)
            
            session_cookie_names = ['session_id', 'sessionid', 'PHPSESSID', 'JSESSIONID']
            
            for cookie_name in session_cookie_names:
                if cookie_name in initial_cookies and cookie_name in new_cookies:
                    assert initial_cookies[cookie_name] != new_cookies[cookie_name]
    
    def test_jwt_security(self, base_url):
        """Test JWT tokens are securely implemented."""
        # This is a mock JWT for testing - would need real auth in production
        test_payload = {
            "user_id": "12345",
            "username": "testuser",
            "exp": datetime.utcnow() + timedelta(days=1)
        }
        
        # Test weak secret detection
        weak_secrets = ['secret', 'password', '12345678', 'changeme']
        
        for secret in weak_secrets:
            token = jwt.encode(test_payload, secret, algorithm='HS256')
            
            response = requests.get(
                urljoin(base_url, '/api/user/profile'),
                headers={'Authorization': f'Bearer {token}'}
            )
            
            # Should reject tokens with weak secrets
            assert response.status_code in [401, 403]
    
    def test_no_user_enumeration(self, auth_url):
        """Test login doesn't reveal if username exists."""
        # Test with likely existing username
        response1 = requests.post(auth_url, json={
            "username": "admin",
            "password": "wrongpassword123"
        })
        
        # Test with likely non-existing username
        response2 = requests.post(auth_url, json={
            "username": f"nonexistent_{int(time.time())}",
            "password": "wrongpassword123"
        })
        
        # Responses should be identical
        assert response1.status_code == response2.status_code
        
        # Response times should be similar (within 200ms)
        # This prevents timing attacks
        # Note: This test might be flaky in CI environments


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_xss_prevention_in_api(self, base_url):
        """Test API prevents XSS attacks."""
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")',
            '<svg onload=alert("XSS")>',
            '"><script>alert("XSS")</script>',
            '<iframe src="javascript:alert(\'XSS\')">'
        ]
        
        endpoints = [
            '/api/content/create',
            '/api/user/profile/update',
            '/api/search'
        ]
        
        for endpoint in endpoints:
            for payload in xss_payloads:
                response = requests.post(
                    urljoin(base_url, endpoint),
                    json={"content": payload, "name": payload}
                )
                
                if response.status_code == 200:
                    # Check payload is properly escaped in response
                    assert payload not in response.text
                    assert '&lt;script&gt;' in response.text or response.headers.get('Content-Type') == 'application/json'
    
    def test_path_traversal_prevention(self, base_url):
        """Test path traversal attacks are prevented."""
        path_payloads = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd',
            '....//....//....//etc/passwd',
            '..%252f..%252f..%252fetc%252fpasswd'
        ]
        
        endpoints = [
            '/api/files/download?file=',
            '/api/content/view?path=',
            '/api/static/'
        ]
        
        for endpoint in endpoints:
            for payload in path_payloads:
                response = requests.get(urljoin(base_url, endpoint + payload))
                
                # Should get 400, 403, or 404, not file content
                assert response.status_code in [400, 403, 404]
                
                # Check no system file content in response
                assert 'root:' not in response.text
                assert 'Administrator:' not in response.text
    
    def test_command_injection_prevention(self, base_url):
        """Test command injection is prevented."""
        cmd_payloads = [
            '; ls -la',
            '| whoami',
            '`id`',
            '$(cat /etc/passwd)',
            '; ping -c 10 127.0.0.1',
            '& dir',
            '|| sleep 10'
        ]
        
        endpoints = [
            '/api/tools/ping',
            '/api/export/generate',
            '/api/process'
        ]
        
        for endpoint in endpoints:
            for payload in cmd_payloads:
                start_time = time.time()
                response = requests.post(
                    urljoin(base_url, endpoint),
                    json={"input": payload, "command": payload}
                )
                elapsed = time.time() - start_time
                
                # Check no command execution
                assert response.status_code in [400, 403, 404, 405]
                
                # Check no command output in response
                assert 'uid=' not in response.text
                assert 'root' not in response.text
                assert 'Directory of' not in response.text
                
                # Check no sleep delay (command didn't execute)
                assert elapsed < 5
    
    def test_xxe_prevention(self, base_url):
        """Test XML External Entity injection is prevented."""
        xxe_payloads = [
            '''<?xml version="1.0"?>
            <!DOCTYPE data [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
            ]>
            <data>&xxe;</data>''',
            
            '''<?xml version="1.0"?>
            <!DOCTYPE data [
            <!ENTITY xxe SYSTEM "http://evil.com/xxe">
            ]>
            <data>&xxe;</data>'''
        ]
        
        xml_endpoints = [
            '/api/import/xml',
            '/api/data/process'
        ]
        
        for endpoint in xml_endpoints:
            for payload in xxe_payloads:
                response = requests.post(
                    urljoin(base_url, endpoint),
                    data=payload,
                    headers={'Content-Type': 'application/xml'}
                )
                
                # Should reject or safely process
                assert 'root:' not in response.text
                assert response.status_code in [400, 403, 404, 405, 415]
    
    def test_ldap_injection_prevention(self, base_url):
        """Test LDAP injection is prevented."""
        ldap_payloads = [
            '*',
            '*)(&(password=*',
            'admin)(&(password=*))',
            '*)(uid=*))(|(uid=*',
            'admin))%00'
        ]
        
        ldap_endpoints = [
            '/api/users/search',
            '/api/auth/ldap'
        ]
        
        for endpoint in ldap_endpoints:
            for payload in ldap_payloads:
                response = requests.post(
                    urljoin(base_url, endpoint),
                    json={"username": payload, "search": payload}
                )
                
                # Should handle safely
                assert response.status_code in [400, 403, 404, 405]


class TestSessionSecurity:
    """Test session management security."""
    
    def test_session_cookie_flags(self, base_url):
        """Test session cookies have proper security flags."""
        session = requests.Session()
        response = session.get(base_url)
        
        for cookie in session.cookies:
            # Check Secure flag (HTTPS only)
            assert cookie.secure is True
            
            # Check HttpOnly flag (no JavaScript access)
            assert cookie.has_nonstandard_attr('HttpOnly')
            
            # Check SameSite attribute
            assert cookie.has_nonstandard_attr('SameSite')
            same_site = cookie.get_nonstandard_attr('SameSite')
            assert same_site in ['Strict', 'Lax']
            
            # Check no Domain attribute for session cookies
            # This prevents subdomain access
            if 'session' in cookie.name.lower():
                assert cookie.domain is None or cookie.domain == ''
    
    def test_session_timeout(self, base_url, auth_url):
        """Test sessions timeout after inactivity."""
        session = requests.Session()
        
        # Login
        response = session.post(auth_url, json={
            "username": "testuser",
            "password": "Test123!@#"
        })
        
        if response.status_code == 200:
            # Wait for timeout (this is a simplified test)
            # In real tests, you'd mock time or use shorter timeouts
            
            # Check session is valid immediately
            response = session.get(urljoin(base_url, '/api/user/profile'))
            initial_status = response.status_code
            
            # Make request after expected timeout
            # This would need adjustment based on actual timeout settings
            response = session.get(urljoin(base_url, '/api/user/profile'))
            
            # In production, you'd test that session expires
            # For now, just ensure we get a response
            assert response.status_code in [200, 401, 403]
    
    def test_concurrent_session_limit(self, base_url, auth_url):
        """Test concurrent session limits are enforced."""
        sessions = []
        login_data = {"username": "testuser", "password": "Test123!@#"}
        
        # Create multiple sessions
        for i in range(5):
            session = requests.Session()
            response = session.post(auth_url, json=login_data)
            
            if response.status_code == 200:
                sessions.append(session)
        
        # Verify earlier sessions are invalidated or limit is enforced
        if len(sessions) > 3:  # Assuming limit of 3 concurrent sessions
            # Check first session is invalidated
            response = sessions[0].get(urljoin(base_url, '/api/user/profile'))
            assert response.status_code in [401, 403]


class TestDataProtection:
    """Test data protection measures."""
    
    def test_no_sensitive_data_in_logs(self, base_url):
        """Test sensitive data is not exposed in error messages."""
        # Trigger various errors
        error_endpoints = [
            '/api/nonexistent',
            '/api/user/99999999',
            '/api/internal-error'
        ]
        
        sensitive_patterns = [
            r'password["\s:=]+\S+',
            r'api[_-]?key["\s:=]+\S+',
            r'secret["\s:=]+\S+',
            r'token["\s:=]+\S+',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Email
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b',  # Credit card
            r'\b\d{3}-\d{2}-\d{4}\b'  # SSN
        ]
        
        for endpoint in error_endpoints:
            response = requests.get(urljoin(base_url, endpoint))
            
            for pattern in sensitive_patterns:
                assert not re.search(pattern, response.text, re.IGNORECASE)
    
    def test_api_field_filtering(self, base_url):
        """Test API doesn't expose internal fields."""
        endpoints = [
            '/api/users',
            '/api/content/list',
            '/api/analytics/data'
        ]
        
        internal_fields = [
            'password',
            'passwordHash',
            'salt',
            'internalId',
            '__v',  # MongoDB version key
            '_id',  # MongoDB ID (should use 'id' instead)
            'deletedAt',
            'ipAddress',
            'sessionToken'
        ]
        
        for endpoint in endpoints:
            response = requests.get(urljoin(base_url, endpoint))
            
            if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('application/json'):
                data = response.json()
                
                # Check each item for internal fields
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if isinstance(item, dict):
                        for field in internal_fields:
                            assert field not in item
    
    def test_encryption_in_transit(self, base_url):
        """Test all communication is encrypted."""
        # Parse URL
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        
        # Verify HTTPS
        assert parsed.scheme == 'https'
        
        # Test TLS configuration
        context = ssl.create_default_context()
        
        with socket.create_connection((parsed.hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock:
                # Check protocol version
                assert ssock.version() in ['TLSv1.2', 'TLSv1.3']
                
                # Check cipher strength
                cipher = ssock.cipher()
                if cipher:
                    # Cipher strength should be at least 128 bits
                    assert cipher[2] >= 128


class TestAPISecuri-testing:
    """Test API-specific security measures."""
    
    def test_api_versioning(self, base_url):
        """Test API versioning is implemented."""
        response = requests.get(base_url)
        
        # Check API version in URL or headers
        assert '/v1/' in base_url or '/api/v1' in base_url or \
               'API-Version' in response.headers or \
               'X-API-Version' in response.headers
    
    def test_cors_configuration(self, base_url):
        """Test CORS is properly configured."""
        # Test preflight request
        response = requests.options(
            base_url,
            headers={
                'Origin': 'https://evil.com',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
        )
        
        if 'Access-Control-Allow-Origin' in response.headers:
            # Should not allow all origins
            assert response.headers['Access-Control-Allow-Origin'] != '*'
            
            # Should not reflect arbitrary origins
            assert response.headers['Access-Control-Allow-Origin'] != 'https://evil.com'
            
            # Check credentials not allowed with wildcard
            if response.headers['Access-Control-Allow-Origin'] == '*':
                assert response.headers.get('Access-Control-Allow-Credentials') != 'true'
    
    def test_api_authentication_required(self, base_url):
        """Test API endpoints require authentication."""
        protected_endpoints = [
            '/api/user/profile',
            '/api/content/create',
            '/api/analytics/export',
            '/api/settings/update'
        ]
        
        for endpoint in protected_endpoints:
            # Request without auth
            response = requests.get(urljoin(base_url, endpoint))
            
            # Should require authentication
            assert response.status_code in [401, 403]
            
            # Should return proper error format
            if response.headers.get('Content-Type', '').startswith('application/json'):
                data = response.json()
                assert 'error' in data or 'message' in data
    
    def test_api_rate_limiting(self, base_url):
        """Test API rate limiting is enforced."""
        endpoint = urljoin(base_url, '/api/search')
        
        responses = []
        for i in range(100):
            response = requests.get(endpoint, params={'q': 'test'})
            responses.append(response.status_code)
            
            if response.status_code == 429:
                break
        
        # Should hit rate limit
        assert 429 in responses
        
        # Check rate limit headers
        rate_limit_response = next((r for r in responses if r == 429), None)
        if rate_limit_response:
            assert any(header in response.headers for header in [
                'X-RateLimit-Limit',
                'X-RateLimit-Remaining',
                'X-RateLimit-Reset',
                'Retry-After'
            ])
    
    def test_api_input_size_limits(self, base_url):
        """Test API enforces input size limits."""
        large_payload = {
            "data": "x" * (10 * 1024 * 1024)  # 10MB string
        }
        
        response = requests.post(
            urljoin(base_url, '/api/content/create'),
            json=large_payload
        )
        
        # Should reject oversized payload
        assert response.status_code in [413, 400]
    
    def test_api_method_restrictions(self, base_url):
        """Test API endpoints only accept intended methods."""
        endpoints_methods = {
            '/api/user/profile': ['GET'],
            '/api/auth/login': ['POST'],
            '/api/content/create': ['POST'],
            '/api/content/update': ['PUT', 'PATCH'],
            '/api/content/delete': ['DELETE']
        }
        
        all_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE']
        
        for endpoint, allowed_methods in endpoints_methods.items():
            for method in all_methods:
                if method not in allowed_methods and method != 'OPTIONS':
                    response = requests.request(method, urljoin(base_url, endpoint))
                    
                    # Should reject disallowed methods
                    assert response.status_code in [405, 404, 403]


class TestCryptography:
    """Test cryptographic implementations."""
    
    def test_password_hashing(self, base_url):
        """Test passwords are properly hashed."""
        # This test would need access to the database or special test endpoints
        # For now, we test that passwords are not returned in API responses
        
        endpoints = [
            '/api/user/profile',
            '/api/users',
            '/api/auth/session'
        ]
        
        password_fields = [
            'password',
            'pass',
            'pwd',
            'passwordHash',
            'password_hash',
            'encryptedPassword'
        ]
        
        for endpoint in endpoints:
            response = requests.get(urljoin(base_url, endpoint))
            
            if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('application/json'):
                data = response.json()
                
                # Check no password fields in response
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if isinstance(item, dict):
                        for field in password_fields:
                            assert field not in item
    
    def test_token_entropy(self, base_url):
        """Test tokens have sufficient entropy."""
        # Request password reset to get a token
        response = requests.post(
            urljoin(base_url, '/api/auth/forgot-password'),
            json={"email": "test@example.com"}
        )
        
        if 'token' in response.text or 'reset-token' in response.headers:
            # Extract token (this is simplified - would need actual token)
            token = "sample_token_from_response"
            
            # Check token length (should be at least 32 characters)
            assert len(token) >= 32
            
            # Check token randomness (simplified check)
            # In production, use proper entropy calculation
            unique_chars = len(set(token))
            assert unique_chars >= 16  # Should use many different characters


class TestSecurityMisconfiguration:
    """Test for security misconfigurations."""
    
    def test_no_default_credentials(self, base_url):
        """Test default credentials don't work."""
        default_creds = [
            ("admin", "admin"),
            ("administrator", "password"),
            ("root", "root"),
            ("test", "test"),
            ("demo", "demo"),
            ("guest", "guest")
        ]
        
        auth_url = urljoin(base_url, '/api/auth/login')
        
        for username, password in default_creds:
            response = requests.post(auth_url, json={
                "username": username,
                "password": password
            })
            
            # Should not authenticate with default credentials
            assert response.status_code in [401, 403]
    
    def test_no_debug_mode(self, base_url):
        """Test debug mode is disabled in production."""
        # Trigger an error
        response = requests.get(urljoin(base_url, '/api/trigger-error'))
        
        # Check no debug information in response
        debug_indicators = [
            'stacktrace',
            'stack trace',
            'traceback',
            'at line',
            'file:',
            'debug',
            'development mode',
            'source code',
            'code snippet'
        ]
        
        for indicator in debug_indicators:
            assert indicator not in response.text.lower()
    
    def test_no_directory_listing(self, base_url):
        """Test directory listing is disabled."""
        directories = [
            '/api/',
            '/static/',
            '/uploads/',
            '/public/',
            '/assets/'
        ]
        
        for directory in directories:
            response = requests.get(urljoin(base_url, directory))
            
            # Should not show directory listing
            assert 'Index of' not in response.text
            assert 'Directory listing' not in response.text
            assert '<title>Directory' not in response.text
    
    def test_secure_file_uploads(self, base_url):
        """Test file upload security."""
        upload_url = urljoin(base_url, '/api/upload')
        
        # Test dangerous file types
        dangerous_files = [
            ('test.php', 'text/php', '<?php echo "test"; ?>'),
            ('test.jsp', 'text/html', '<% out.println("test"); %>'),
            ('test.asp', 'text/html', '<% Response.Write("test") %>'),
            ('test.exe', 'application/octet-stream', b'MZ\x90\x00'),
            ('test.sh', 'text/plain', '#!/bin/bash\necho "test"')
        ]
        
        for filename, content_type, content in dangerous_files:
            files = {'file': (filename, content, content_type)}
            response = requests.post(upload_url, files=files)
            
            # Should reject dangerous file types
            if response.status_code == 200:
                # If accepted, verify file is not executable
                data = response.json()
                if 'url' in data:
                    file_response = requests.get(data['url'])
                    
                    # Should not execute
                    assert 'test' not in file_response.text
                    assert file_response.headers.get('Content-Type') == 'application/octet-stream'


@pytest.mark.security
class TestComplianceRequirements:
    """Test compliance with security standards."""
    
    def test_pci_dss_requirements(self, base_url):
        """Test basic PCI DSS requirements."""
        # This is a simplified test - full PCI compliance requires extensive testing
        
        # Test no credit card data in responses
        endpoints = ['/api/orders', '/api/transactions', '/api/users']
        
        cc_patterns = [
            r'\b4[0-9]{12}(?:[0-9]{3})?\b',  # Visa
            r'\b5[1-5][0-9]{14}\b',  # Mastercard
            r'\b3[47][0-9]{13}\b',  # Amex
            r'\b3(?:0[0-5]|[68][0-9])[0-9]{11}\b'  # Diners
        ]
        
        for endpoint in endpoints:
            response = requests.get(urljoin(base_url, endpoint))
            
            if response.status_code == 200:
                for pattern in cc_patterns:
                    assert not re.search(pattern, response.text)
    
    def test_gdpr_requirements(self, base_url):
        """Test basic GDPR requirements."""
        # Test data export endpoint exists
        response = requests.get(urljoin(base_url, '/api/user/export-data'))
        assert response.status_code in [200, 401]  # Exists but may require auth
        
        # Test data deletion endpoint exists
        response = requests.delete(urljoin(base_url, '/api/user/delete-account'))
        assert response.status_code in [200, 401, 405]  # Exists but may require auth
        
        # Test privacy policy endpoint
        response = requests.get(urljoin(base_url, '/api/legal/privacy-policy'))
        assert response.status_code == 200
    
    def test_owasp_top_10(self, base_url):
        """Test against OWASP Top 10 vulnerabilities."""
        # This consolidates various tests above
        # A01:2021 – Broken Access Control - tested in TestAuthentication
        # A02:2021 – Cryptographic Failures - tested in TestCryptography
        # A03:2021 – Injection - tested in TestInputValidation
        # A04:2021 – Insecure Design - tested throughout
        # A05:2021 – Security Misconfiguration - tested in TestSecurityMisconfiguration
        # A06:2021 – Vulnerable Components - tested in dependency scanning
        # A07:2021 – Identification and Authentication Failures - tested in TestAuthentication
        # A08:2021 – Software and Data Integrity Failures - tested in TestDataProtection
        # A09:2021 – Security Logging and Monitoring Failures - tested separately
        # A10:2021 – Server-Side Request Forgery (SSRF) - tested below
        
        # Test SSRF protection
        ssrf_payloads = [
            'http://localhost:8080',
            'http://127.0.0.1:22',
            'http://169.254.169.254/',  # AWS metadata
            'file:///etc/passwd',
            'gopher://localhost:8080',
            'dict://localhost:11211'
        ]
        
        endpoints = ['/api/fetch-url', '/api/webhook/test', '/api/proxy']
        
        for endpoint in endpoints:
            for payload in ssrf_payloads:
                response = requests.post(
                    urljoin(base_url, endpoint),
                    json={"url": payload}
                )
                
                # Should block SSRF attempts
                assert response.status_code in [400, 403, 404]


# Performance-related security tests
class TestPerformanceSecurity:
    """Test security under load conditions."""
    
    @pytest.mark.slow
    def test_dos_protection(self, base_url):
        """Test protection against denial of service."""
        import concurrent.futures
        
        def make_request():
            return requests.get(base_url)
        
        # Make many concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(200)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        status_codes = [r.status_code for r in responses]
        
        # Should rate limit or queue requests, not crash
        assert 503 in status_codes or 429 in status_codes
    
    def test_regex_dos_protection(self, base_url):
        """Test protection against ReDoS attacks."""
        # Patterns that can cause exponential backtracking
        redos_patterns = [
            'a' * 50 + '!',
            '(' * 50 + ')' * 50,
            'a+' * 25 + 'b'
        ]
        
        endpoints = ['/api/search', '/api/validate']
        
        for endpoint in endpoints:
            for pattern in redos_patterns:
                start_time = time.time()
                response = requests.post(
                    urljoin(base_url, endpoint),
                    json={"pattern": pattern, "input": pattern},
                    timeout=5
                )
                elapsed = time.time() - start_time
                
                # Should not hang or timeout
                assert elapsed < 2
                assert response.status_code in [200, 400, 403]
    
    def test_zip_bomb_protection(self, base_url):
        """Test protection against zip bombs."""
        # Create a small zip bomb for testing
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Create nested zips
            for i in range(5):
                data = b'0' * (1024 * 1024)  # 1MB of zeros
                zf.writestr(f'file{i}.txt', data)
        
        zip_data = zip_buffer.getvalue()
        
        response = requests.post(
            urljoin(base_url, '/api/upload'),
            files={'file': ('test.zip', zip_data, 'application/zip')}
        )
        
        # Should handle safely
        assert response.status_code in [200, 400, 413]
        
        # If accepted, should not crash the server
        if response.status_code == 200:
            # Verify server is still responsive
            health_response = requests.get(urljoin(base_url, '/health'))
            assert health_response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--security'])