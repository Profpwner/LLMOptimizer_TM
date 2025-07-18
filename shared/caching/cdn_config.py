"""
CDN configuration for CloudFront and Cloudflare.
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import logging

logger = logging.getLogger(__name__)


class CDNProvider(Enum):
    """Supported CDN providers."""
    CLOUDFRONT = "cloudfront"
    CLOUDFLARE = "cloudflare"
    FASTLY = "fastly"
    AKAMAI = "akamai"


@dataclass
class CacheRule:
    """CDN cache rule configuration."""
    path_pattern: str
    cache_behavior: str = "cache"  # cache, no-cache, bypass
    ttl: int = 3600  # 1 hour default
    browser_ttl: int = 300  # 5 minutes default
    edge_ttl: int = 3600
    respect_headers: bool = True
    query_string_handling: str = "include"  # include, exclude, include-list
    query_string_list: List[str] = field(default_factory=list)
    compress: bool = True
    allowed_methods: List[str] = field(default_factory=lambda: ["GET", "HEAD"])
    cached_methods: List[str] = field(default_factory=lambda: ["GET", "HEAD"])
    headers_to_forward: List[str] = field(default_factory=list)
    cookies_to_forward: str = "none"  # none, all, whitelist
    cookie_whitelist: List[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """CDN security configuration."""
    enable_waf: bool = True
    waf_rules: List[str] = field(default_factory=list)
    geo_restrictions: List[str] = field(default_factory=list)  # Country codes
    ip_whitelist: List[str] = field(default_factory=list)
    ip_blacklist: List[str] = field(default_factory=list)
    enable_ddos_protection: bool = True
    enable_bot_management: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)
    enable_signed_urls: bool = False
    signed_url_ttl: int = 3600


@dataclass
class PerformanceConfig:
    """CDN performance configuration."""
    enable_http2: bool = True
    enable_http3: bool = True
    enable_brotli: bool = True
    enable_gzip: bool = True
    enable_webp: bool = True
    enable_image_optimization: bool = True
    enable_minification: bool = True
    minify_html: bool = True
    minify_css: bool = True
    minify_js: bool = True
    enable_early_hints: bool = True
    enable_server_push: bool = False
    push_resources: List[str] = field(default_factory=list)


@dataclass
class OriginConfig:
    """Origin server configuration."""
    domain: str
    protocol: str = "https"
    port: int = 443
    path: str = ""
    custom_headers: Dict[str, str] = field(default_factory=dict)
    connection_timeout: int = 10
    read_timeout: int = 30
    keepalive_timeout: int = 5
    ssl_protocols: List[str] = field(default_factory=lambda: ["TLSv1.2", "TLSv1.3"])
    origin_shield: bool = False
    origin_shield_region: Optional[str] = None


class CDNConfig:
    """
    CDN configuration manager for multiple providers.
    """
    
    def __init__(self, provider: CDNProvider):
        self.provider = provider
        self.distributions: Dict[str, Dict[str, Any]] = {}
        self.cache_rules: List[CacheRule] = []
        self.security_config = SecurityConfig()
        self.performance_config = PerformanceConfig()
        self.origin_configs: Dict[str, OriginConfig] = {}
        
        # Provider-specific settings
        self.provider_config = self._load_provider_config()
    
    def _load_provider_config(self) -> Dict[str, Any]:
        """Load provider-specific configuration."""
        configs = {
            CDNProvider.CLOUDFRONT: {
                'distribution_id': os.getenv('CLOUDFRONT_DISTRIBUTION_ID'),
                'origin_access_identity': os.getenv('CLOUDFRONT_OAI'),
                'key_pair_id': os.getenv('CLOUDFRONT_KEY_PAIR_ID'),
                'private_key_path': os.getenv('CLOUDFRONT_PRIVATE_KEY_PATH'),
                'default_root_object': 'index.html',
                'price_class': 'PriceClass_All',
                'enable_ipv6': True,
                'viewer_protocol_policy': 'redirect-to-https',
                'allowed_methods': ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
                'cached_methods': ['GET', 'HEAD', 'OPTIONS'],
                'compress': True,
                'viewer_certificate': {
                    'cloudfront_default_certificate': True,
                    'minimum_protocol_version': 'TLSv1.2_2021'
                }
            },
            CDNProvider.CLOUDFLARE: {
                'zone_id': os.getenv('CLOUDFLARE_ZONE_ID'),
                'api_token': os.getenv('CLOUDFLARE_API_TOKEN'),
                'account_id': os.getenv('CLOUDFLARE_ACCOUNT_ID'),
                'caching_level': 'standard',  # no-query-string, ignore-query-string, standard
                'browser_cache_ttl': 14400,  # 4 hours
                'edge_cache_ttl': 7200,  # 2 hours
                'always_online': True,
                'development_mode': False,
                'minify': {
                    'css': True,
                    'html': True,
                    'js': True
                },
                'polish': 'lossless',  # off, lossless, lossy
                'webp': True,
                'brotli': True,
                'rocket_loader': True,
                'security_level': 'medium',  # off, essentially_off, low, medium, high, under_attack
                'ssl': 'full',  # off, flexible, full, strict
                'tls_1_3': True,
                'automatic_https_rewrites': True,
                'opportunistic_encryption': True,
                'cache_level': 'aggressive',
                'tiered_caching': True,
                'argo': True,
                'http3': True
            }
        }
        
        return configs.get(self.provider, {})
    
    def add_cache_rule(self, rule: CacheRule):
        """Add a cache rule."""
        self.cache_rules.append(rule)
        logger.info(f"Added cache rule for pattern: {rule.path_pattern}")
    
    def generate_cloudfront_config(self) -> Dict[str, Any]:
        """Generate CloudFront distribution configuration."""
        behaviors = []
        
        # Default cache behavior
        default_behavior = {
            'TargetOriginId': 'default-origin',
            'ViewerProtocolPolicy': self.provider_config['viewer_protocol_policy'],
            'AllowedMethods': self.provider_config['allowed_methods'],
            'CachedMethods': self.provider_config['cached_methods'],
            'Compress': self.provider_config['compress'],
            'ForwardedValues': {
                'QueryString': True,
                'Cookies': {'Forward': 'none'},
                'Headers': ['Origin', 'Access-Control-Request-Method', 'Access-Control-Request-Headers']
            },
            'MinTTL': 0,
            'DefaultTTL': 86400,
            'MaxTTL': 31536000,
            'TrustedSigners': {
                'Enabled': self.security_config.enable_signed_urls,
                'Quantity': 0
            }
        }
        
        # Custom cache behaviors from rules
        for i, rule in enumerate(self.cache_rules):
            behavior = {
                'PathPattern': rule.path_pattern,
                'TargetOriginId': 'default-origin',
                'ViewerProtocolPolicy': 'redirect-to-https',
                'AllowedMethods': rule.allowed_methods,
                'CachedMethods': rule.cached_methods,
                'Compress': rule.compress,
                'ForwardedValues': {
                    'QueryString': rule.query_string_handling != 'exclude',
                    'QueryStringCacheKeys': rule.query_string_list if rule.query_string_handling == 'include-list' else [],
                    'Cookies': {
                        'Forward': rule.cookies_to_forward,
                        'WhitelistedNames': rule.cookie_whitelist if rule.cookies_to_forward == 'whitelist' else []
                    },
                    'Headers': rule.headers_to_forward
                },
                'MinTTL': 0,
                'DefaultTTL': rule.ttl,
                'MaxTTL': rule.edge_ttl
            }
            behaviors.append(behavior)
        
        # Origins configuration
        origins = []
        for name, origin in self.origin_configs.items():
            origin_config = {
                'Id': name,
                'DomainName': origin.domain,
                'CustomOriginConfig': {
                    'HTTPPort': 80,
                    'HTTPSPort': origin.port,
                    'OriginProtocolPolicy': f"{origin.protocol}-only",
                    'OriginSslProtocols': origin.ssl_protocols,
                    'OriginReadTimeout': origin.read_timeout,
                    'OriginKeepaliveTimeout': origin.keepalive_timeout
                },
                'CustomHeaders': [
                    {'HeaderName': k, 'HeaderValue': v}
                    for k, v in origin.custom_headers.items()
                ]
            }
            
            if origin.origin_shield:
                origin_config['OriginShield'] = {
                    'Enabled': True,
                    'OriginShieldRegion': origin.origin_shield_region or 'us-east-1'
                }
            
            origins.append(origin_config)
        
        # Complete distribution config
        config = {
            'CallerReference': f"llmoptimizer-{int(time.time())}",
            'DefaultRootObject': self.provider_config['default_root_object'],
            'Origins': origins,
            'DefaultCacheBehavior': default_behavior,
            'CacheBehaviors': behaviors,
            'CustomErrorResponses': [
                {
                    'ErrorCode': 404,
                    'ResponsePagePath': '/404.html',
                    'ResponseCode': '404',
                    'ErrorCachingMinTTL': 300
                },
                {
                    'ErrorCode': 500,
                    'ResponsePagePath': '/500.html',
                    'ResponseCode': '500',
                    'ErrorCachingMinTTL': 0
                }
            ],
            'Comment': 'LLMOptimizer CDN Distribution',
            'PriceClass': self.provider_config['price_class'],
            'Enabled': True,
            'ViewerCertificate': self.provider_config['viewer_certificate'],
            'HttpVersion': 'http2and3' if self.performance_config.enable_http3 else 'http2',
            'IsIPV6Enabled': self.provider_config['enable_ipv6']
        }
        
        # Add WAF if enabled
        if self.security_config.enable_waf:
            config['WebACLId'] = os.getenv('AWS_WAF_WEB_ACL_ID', '')
        
        # Add geo restrictions
        if self.security_config.geo_restrictions:
            config['Restrictions'] = {
                'GeoRestriction': {
                    'RestrictionType': 'blacklist',
                    'Quantity': len(self.security_config.geo_restrictions),
                    'Items': self.security_config.geo_restrictions
                }
            }
        
        return config
    
    def generate_cloudflare_config(self) -> Dict[str, Any]:
        """Generate Cloudflare configuration."""
        # Page rules for cache behaviors
        page_rules = []
        
        for rule in self.cache_rules:
            page_rule = {
                'targets': [
                    {
                        'target': 'url',
                        'constraint': {
                            'operator': 'matches',
                            'value': f"*{rule.path_pattern}"
                        }
                    }
                ],
                'actions': [
                    {
                        'id': 'cache_level',
                        'value': 'cache_everything' if rule.cache_behavior == 'cache' else 'bypass'
                    },
                    {
                        'id': 'edge_cache_ttl',
                        'value': rule.edge_ttl
                    },
                    {
                        'id': 'browser_cache_ttl',
                        'value': rule.browser_ttl
                    }
                ],
                'priority': len(page_rules) + 1,
                'status': 'active'
            }
            
            if rule.compress:
                page_rule['actions'].append({
                    'id': 'automatic_https_rewrites',
                    'value': 'on'
                })
            
            page_rules.append(page_rule)
        
        # Zone settings
        zone_settings = {
            'always_online': self.provider_config['always_online'],
            'brotli': self.provider_config['brotli'],
            'browser_cache_ttl': self.provider_config['browser_cache_ttl'],
            'cache_level': self.provider_config['cache_level'],
            'development_mode': self.provider_config['development_mode'],
            'edge_cache_ttl': self.provider_config['edge_cache_ttl'],
            'http3': self.provider_config['http3'],
            'minify': self.provider_config['minify'],
            'opportunistic_encryption': self.provider_config['opportunistic_encryption'],
            'polish': self.provider_config['polish'],
            'rocket_loader': self.provider_config['rocket_loader'],
            'security_level': self.provider_config['security_level'],
            'ssl': self.provider_config['ssl'],
            'tls_1_3': self.provider_config['tls_1_3'],
            'webp': self.provider_config['webp']
        }
        
        # Firewall rules
        firewall_rules = []
        
        if self.security_config.ip_whitelist:
            firewall_rules.append({
                'description': 'IP Whitelist',
                'expression': f"(not ip.src in {{{' '.join(self.security_config.ip_whitelist)}}})",
                'action': 'block'
            })
        
        if self.security_config.ip_blacklist:
            firewall_rules.append({
                'description': 'IP Blacklist',
                'expression': f"(ip.src in {{{' '.join(self.security_config.ip_blacklist)}}})",
                'action': 'block'
            })
        
        # Workers for advanced caching
        worker_script = self._generate_cloudflare_worker()
        
        return {
            'zone_id': self.provider_config['zone_id'],
            'zone_settings': zone_settings,
            'page_rules': page_rules,
            'firewall_rules': firewall_rules,
            'worker_script': worker_script,
            'argo': self.provider_config['argo'],
            'tiered_caching': self.provider_config['tiered_caching']
        }
    
    def _generate_cloudflare_worker(self) -> str:
        """Generate Cloudflare Worker script for advanced caching."""
        return '''
addEventListener('fetch', event => {
    event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
    const url = new URL(request.url)
    
    // Custom cache key
    const cacheKey = new Request(url.toString(), request)
    const cache = caches.default
    
    // Check cache
    let response = await cache.match(cacheKey)
    
    if (!response) {
        // Cache miss - fetch from origin
        response = await fetch(request)
        
        // Clone response for caching
        const responseToCache = response.clone()
        
        // Custom cache headers
        const headers = new Headers(responseToCache.headers)
        headers.set('Cache-Control', 'public, max-age=3600')
        headers.set('X-Cache-Status', 'MISS')
        
        // Cache the response
        event.waitUntil(cache.put(cacheKey, new Response(responseToCache.body, {
            status: responseToCache.status,
            statusText: responseToCache.statusText,
            headers: headers
        })))
    } else {
        // Cache hit
        const headers = new Headers(response.headers)
        headers.set('X-Cache-Status', 'HIT')
        
        response = new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: headers
        })
    }
    
    return response
}
'''
    
    def generate_cache_headers(self, content_type: str) -> Dict[str, str]:
        """Generate optimal cache headers for content type."""
        headers = {
            'Vary': 'Accept-Encoding',
            'X-Content-Type-Options': 'nosniff'
        }
        
        # Content-specific cache settings
        if content_type.startswith('image/'):
            headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif content_type.startswith('text/css') or content_type.startswith('application/javascript'):
            headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif content_type.startswith('font/'):
            headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif content_type == 'text/html':
            headers['Cache-Control'] = 'public, max-age=3600, must-revalidate'
        elif content_type.startswith('application/json'):
            headers['Cache-Control'] = 'public, max-age=300, must-revalidate'
        else:
            headers['Cache-Control'] = 'public, max-age=86400'
        
        # Security headers
        if self.security_config.custom_headers:
            headers.update(self.security_config.custom_headers)
        
        return headers
    
    def generate_signed_url(self, url: str, expires_in: int = 3600) -> str:
        """Generate signed URL for secure content delivery."""
        if self.provider == CDNProvider.CLOUDFRONT:
            return self._generate_cloudfront_signed_url(url, expires_in)
        elif self.provider == CDNProvider.CLOUDFLARE:
            return self._generate_cloudflare_signed_url(url, expires_in)
        else:
            logger.warning(f"Signed URLs not implemented for {self.provider.value}")
            return url
    
    def _generate_cloudfront_signed_url(self, url: str, expires_in: int) -> str:
        """Generate CloudFront signed URL."""
        # This would use boto3 CloudFront signer
        # Simplified example
        import time
        expires = int(time.time()) + expires_in
        
        # In production, use proper CloudFront signing
        signature = hashlib.sha256(f"{url}{expires}".encode()).hexdigest()
        
        return f"{url}?Expires={expires}&Signature={signature}&Key-Pair-Id={self.provider_config['key_pair_id']}"
    
    def _generate_cloudflare_signed_url(self, url: str, expires_in: int) -> str:
        """Generate Cloudflare signed URL using Workers."""
        # This would be implemented in Cloudflare Worker
        # Simplified example
        import time
        expires = int(time.time()) + expires_in
        
        token = hashlib.sha256(f"{url}{expires}{self.provider_config['api_token']}".encode()).hexdigest()
        
        return f"{url}?token={token}&expires={expires}"
    
    def invalidate_cache(self, paths: List[str]):
        """Invalidate CDN cache for specific paths."""
        if self.provider == CDNProvider.CLOUDFRONT:
            self._invalidate_cloudfront(paths)
        elif self.provider == CDNProvider.CLOUDFLARE:
            self._invalidate_cloudflare(paths)
    
    def _invalidate_cloudfront(self, paths: List[str]):
        """Invalidate CloudFront cache."""
        # This would use boto3
        logger.info(f"Invalidating CloudFront paths: {paths}")
    
    def _invalidate_cloudflare(self, paths: List[str]):
        """Invalidate Cloudflare cache."""
        # This would use Cloudflare API
        logger.info(f"Invalidating Cloudflare paths: {paths}")


# Pre-configured CDN settings for common scenarios
def get_static_assets_config() -> List[CacheRule]:
    """Get cache rules optimized for static assets."""
    return [
        CacheRule(
            path_pattern="*.jpg",
            ttl=31536000,  # 1 year
            browser_ttl=86400,  # 1 day
            edge_ttl=31536000,
            query_string_handling="exclude"
        ),
        CacheRule(
            path_pattern="*.png",
            ttl=31536000,
            browser_ttl=86400,
            edge_ttl=31536000,
            query_string_handling="exclude"
        ),
        CacheRule(
            path_pattern="*.css",
            ttl=31536000,
            browser_ttl=3600,
            edge_ttl=31536000,
            query_string_handling="include"  # For versioning
        ),
        CacheRule(
            path_pattern="*.js",
            ttl=31536000,
            browser_ttl=3600,
            edge_ttl=31536000,
            query_string_handling="include"
        ),
        CacheRule(
            path_pattern="*.woff2",
            ttl=31536000,
            browser_ttl=31536000,
            edge_ttl=31536000,
            query_string_handling="exclude"
        )
    ]


def get_api_config() -> List[CacheRule]:
    """Get cache rules optimized for API responses."""
    return [
        CacheRule(
            path_pattern="/api/v1/public/*",
            ttl=300,  # 5 minutes
            browser_ttl=0,  # No browser cache
            edge_ttl=300,
            query_string_handling="include",
            headers_to_forward=["Authorization", "X-API-Key"],
            cache_behavior="cache"
        ),
        CacheRule(
            path_pattern="/api/v1/user/*",
            cache_behavior="no-cache",  # User-specific, don't cache
            headers_to_forward=["Authorization", "Cookie"],
            cookies_to_forward="all"
        ),
        CacheRule(
            path_pattern="/api/v1/search/*",
            ttl=60,  # 1 minute
            browser_ttl=0,
            edge_ttl=60,
            query_string_handling="include",
            cache_behavior="cache"
        )
    ]