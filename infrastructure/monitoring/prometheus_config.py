"""
Prometheus configuration and metrics exporter.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging
from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    CollectorRegistry, generate_latest,
    start_http_server, push_to_gateway
)
import time

logger = logging.getLogger(__name__)


@dataclass
class ScrapeConfig:
    """Prometheus scrape configuration."""
    job_name: str
    scrape_interval: str = "15s"
    scrape_timeout: str = "10s"
    metrics_path: str = "/metrics"
    scheme: str = "http"
    static_configs: List[Dict[str, Any]] = field(default_factory=list)
    relabel_configs: List[Dict[str, Any]] = field(default_factory=list)
    metric_relabel_configs: List[Dict[str, Any]] = field(default_factory=list)
    tls_config: Optional[Dict[str, Any]] = None
    bearer_token: Optional[str] = None
    basic_auth: Optional[Dict[str, str]] = None


@dataclass
class PrometheusConfig:
    """Complete Prometheus configuration."""
    global_config: Dict[str, Any] = field(default_factory=dict)
    scrape_configs: List[ScrapeConfig] = field(default_factory=list)
    alerting_config: Dict[str, Any] = field(default_factory=dict)
    rule_files: List[str] = field(default_factory=list)
    remote_write: List[Dict[str, Any]] = field(default_factory=list)
    remote_read: List[Dict[str, Any]] = field(default_factory=list)
    storage: Dict[str, Any] = field(default_factory=dict)


class PrometheusConfigBuilder:
    """Builder for Prometheus configuration optimized for 100K+ users."""
    
    def __init__(self):
        self.config = PrometheusConfig()
        self._set_default_global_config()
    
    def _set_default_global_config(self):
        """Set default global configuration."""
        self.config.global_config = {
            'scrape_interval': '15s',
            'evaluation_interval': '15s',
            'scrape_timeout': '10s',
            'external_labels': {
                'monitor': 'llmoptimizer',
                'environment': os.getenv('ENVIRONMENT', 'production')
            }
        }
    
    def add_scrape_config(self, scrape_config: ScrapeConfig) -> 'PrometheusConfigBuilder':
        """Add scrape configuration."""
        self.config.scrape_configs.append(scrape_config)
        return self
    
    def add_kubernetes_sd(self) -> 'PrometheusConfigBuilder':
        """Add Kubernetes service discovery configuration."""
        k8s_api_config = ScrapeConfig(
            job_name='kubernetes-apiservers',
            scheme='https',
            static_configs=[],
            relabel_configs=[
                {
                    'source_labels': ['__meta_kubernetes_namespace', '__meta_kubernetes_service_name', '__meta_kubernetes_endpoint_port_name'],
                    'action': 'keep',
                    'regex': 'default;kubernetes;https'
                }
            ]
        )
        
        k8s_nodes_config = ScrapeConfig(
            job_name='kubernetes-nodes',
            scheme='https',
            static_configs=[],
            relabel_configs=[
                {
                    'action': 'labelmap',
                    'regex': '__meta_kubernetes_node_label_(.+)'
                },
                {
                    'target_label': '__address__',
                    'replacement': 'kubernetes.default.svc:443'
                },
                {
                    'source_labels': ['__meta_kubernetes_node_name'],
                    'regex': '(.+)',
                    'target_label': '__metrics_path__',
                    'replacement': '/api/v1/nodes/${1}/proxy/metrics'
                }
            ]
        )
        
        k8s_pods_config = ScrapeConfig(
            job_name='kubernetes-pods',
            static_configs=[],
            relabel_configs=[
                {
                    'source_labels': ['__meta_kubernetes_pod_annotation_prometheus_io_scrape'],
                    'action': 'keep',
                    'regex': 'true'
                },
                {
                    'source_labels': ['__meta_kubernetes_pod_annotation_prometheus_io_path'],
                    'action': 'replace',
                    'target_label': '__metrics_path__',
                    'regex': '(.+)'
                },
                {
                    'source_labels': ['__address__', '__meta_kubernetes_pod_annotation_prometheus_io_port'],
                    'action': 'replace',
                    'regex': '([^:]+)(?::\\d+)?;(\\d+)',
                    'replacement': '$1:$2',
                    'target_label': '__address__'
                },
                {
                    'action': 'labelmap',
                    'regex': '__meta_kubernetes_pod_label_(.+)'
                },
                {
                    'source_labels': ['__meta_kubernetes_namespace'],
                    'action': 'replace',
                    'target_label': 'kubernetes_namespace'
                },
                {
                    'source_labels': ['__meta_kubernetes_pod_name'],
                    'action': 'replace',
                    'target_label': 'kubernetes_pod_name'
                }
            ]
        )
        
        self.config.scrape_configs.extend([
            k8s_api_config,
            k8s_nodes_config,
            k8s_pods_config
        ])
        
        return self
    
    def add_service_discovery(self, services: List[Dict[str, Any]]) -> 'PrometheusConfigBuilder':
        """Add service discovery for microservices."""
        for service in services:
            scrape_config = ScrapeConfig(
                job_name=service['name'],
                scrape_interval=service.get('interval', '15s'),
                metrics_path=service.get('path', '/metrics'),
                static_configs=[{
                    'targets': service['targets'],
                    'labels': service.get('labels', {})
                }]
            )
            self.config.scrape_configs.append(scrape_config)
        
        return self
    
    def configure_alerting(self, alertmanager_url: str) -> 'PrometheusConfigBuilder':
        """Configure alerting."""
        self.config.alerting_config = {
            'alertmanagers': [{
                'static_configs': [{
                    'targets': [alertmanager_url]
                }]
            }]
        }
        return self
    
    def add_remote_write(self, endpoints: List[Dict[str, Any]]) -> 'PrometheusConfigBuilder':
        """Add remote write endpoints for long-term storage."""
        for endpoint in endpoints:
            remote_write_config = {
                'url': endpoint['url'],
                'remote_timeout': endpoint.get('timeout', '30s'),
                'write_relabel_configs': endpoint.get('relabel_configs', [])
            }
            
            if 'basic_auth' in endpoint:
                remote_write_config['basic_auth'] = endpoint['basic_auth']
            
            if 'bearer_token' in endpoint:
                remote_write_config['bearer_token'] = endpoint['bearer_token']
            
            self.config.remote_write.append(remote_write_config)
        
        return self
    
    def configure_storage(self, retention: str = "15d", chunk_encoding: str = "snappy") -> 'PrometheusConfigBuilder':
        """Configure storage settings."""
        self.config.storage = {
            'tsdb': {
                'retention': retention,
                'chunk_encoding': chunk_encoding,
                'wal_compression': True
            }
        }
        return self
    
    def add_rule_files(self, rule_files: List[str]) -> 'PrometheusConfigBuilder':
        """Add rule files for recording rules and alerts."""
        self.config.rule_files.extend(rule_files)
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build Prometheus configuration."""
        config = {
            'global': self.config.global_config,
            'scrape_configs': []
        }
        
        # Convert scrape configs
        for scrape in self.config.scrape_configs:
            scrape_dict = {
                'job_name': scrape.job_name,
                'scrape_interval': scrape.scrape_interval,
                'scrape_timeout': scrape.scrape_timeout,
                'metrics_path': scrape.metrics_path,
                'scheme': scrape.scheme
            }
            
            if scrape.static_configs:
                scrape_dict['static_configs'] = scrape.static_configs
            
            if scrape.relabel_configs:
                scrape_dict['relabel_configs'] = scrape.relabel_configs
            
            if scrape.metric_relabel_configs:
                scrape_dict['metric_relabel_configs'] = scrape.metric_relabel_configs
            
            config['scrape_configs'].append(scrape_dict)
        
        # Add other configurations
        if self.config.alerting_config:
            config['alerting'] = self.config.alerting_config
        
        if self.config.rule_files:
            config['rule_files'] = self.config.rule_files
        
        if self.config.remote_write:
            config['remote_write'] = self.config.remote_write
        
        if self.config.remote_read:
            config['remote_read'] = self.config.remote_read
        
        if self.config.storage:
            config['storage'] = self.config.storage
        
        return config
    
    def save_to_file(self, filepath: str):
        """Save configuration to file."""
        config = self.build()
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info(f"Prometheus configuration saved to {filepath}")


class MetricsExporter:
    """Custom metrics exporter for application metrics."""
    
    def __init__(self, port: int = 8000, namespace: str = "llmoptimizer"):
        self.port = port
        self.namespace = namespace
        self.registry = CollectorRegistry()
        
        # Define metrics
        self._define_metrics()
    
    def _define_metrics(self):
        """Define application metrics."""
        # Request metrics
        self.request_count = Counter(
            f'{self.namespace}_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            f'{self.namespace}_http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry
        )
        
        # System metrics
        self.active_connections = Gauge(
            f'{self.namespace}_active_connections',
            'Number of active connections',
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            f'{self.namespace}_memory_usage_bytes',
            'Memory usage in bytes',
            ['type'],
            registry=self.registry
        )
        
        self.cpu_usage = Gauge(
            f'{self.namespace}_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        # Business metrics
        self.active_users = Gauge(
            f'{self.namespace}_active_users',
            'Number of active users',
            registry=self.registry
        )
        
        self.llm_requests = Counter(
            f'{self.namespace}_llm_requests_total',
            'Total LLM API requests',
            ['provider', 'model', 'status'],
            registry=self.registry
        )
        
        self.llm_tokens = Counter(
            f'{self.namespace}_llm_tokens_total',
            'Total LLM tokens used',
            ['provider', 'model', 'type'],
            registry=self.registry
        )
        
        self.llm_latency = Histogram(
            f'{self.namespace}_llm_request_latency_seconds',
            'LLM request latency',
            ['provider', 'model'],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_hits = Counter(
            f'{self.namespace}_cache_hits_total',
            'Total cache hits',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_misses = Counter(
            f'{self.namespace}_cache_misses_total',
            'Total cache misses',
            ['cache_type'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_connections = Gauge(
            f'{self.namespace}_db_connections',
            'Database connections',
            ['database', 'state'],
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            f'{self.namespace}_db_query_duration_seconds',
            'Database query duration',
            ['database', 'operation'],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
            registry=self.registry
        )
        
        # Error metrics
        self.errors = Counter(
            f'{self.namespace}_errors_total',
            'Total errors',
            ['type', 'service'],
            registry=self.registry
        )
    
    def start_server(self):
        """Start metrics HTTP server."""
        start_http_server(self.port, registry=self.registry)
        logger.info(f"Metrics server started on port {self.port}")
    
    def push_to_gateway(self, gateway_url: str, job: str):
        """Push metrics to Pushgateway."""
        push_to_gateway(gateway_url, job=job, registry=self.registry)
    
    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry)
    
    # Convenience methods for updating metrics
    def track_request(self, method: str, endpoint: str, status: int, duration: float):
        """Track HTTP request."""
        self.request_count.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        self.request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    
    def track_llm_request(self, provider: str, model: str, status: str, latency: float, tokens: Dict[str, int]):
        """Track LLM request."""
        self.llm_requests.labels(provider=provider, model=model, status=status).inc()
        self.llm_latency.labels(provider=provider, model=model).observe(latency)
        
        for token_type, count in tokens.items():
            self.llm_tokens.labels(provider=provider, model=model, type=token_type).inc(count)
    
    def track_cache_access(self, cache_type: str, hit: bool):
        """Track cache access."""
        if hit:
            self.cache_hits.labels(cache_type=cache_type).inc()
        else:
            self.cache_misses.labels(cache_type=cache_type).inc()
    
    def track_error(self, error_type: str, service: str):
        """Track error occurrence."""
        self.errors.labels(type=error_type, service=service).inc()


def create_prometheus_config_for_k8s() -> Dict[str, Any]:
    """Create Prometheus configuration optimized for Kubernetes."""
    builder = PrometheusConfigBuilder()
    
    # Add Kubernetes service discovery
    builder.add_kubernetes_sd()
    
    # Add microservices
    services = [
        {
            'name': 'api-gateway',
            'targets': ['api-gateway:8080'],
            'labels': {'service': 'api-gateway'}
        },
        {
            'name': 'auth-service',
            'targets': ['auth-service:8080'],
            'labels': {'service': 'auth-service'}
        },
        {
            'name': 'content-service',
            'targets': ['content-service:8080'],
            'labels': {'service': 'content-service'}
        },
        {
            'name': 'ml-service',
            'targets': ['ml-service:8080'],
            'labels': {'service': 'ml-service'}
        },
        {
            'name': 'analytics-service',
            'targets': ['analytics-service:8080'],
            'labels': {'service': 'analytics-service'}
        }
    ]
    builder.add_service_discovery(services)
    
    # Configure alerting
    builder.configure_alerting('alertmanager:9093')
    
    # Add remote storage for long-term retention
    builder.add_remote_write([{
        'url': 'http://thanos-receive:19291/api/v1/receive',
        'timeout': '30s'
    }])
    
    # Configure storage
    builder.configure_storage(retention='15d')
    
    # Add rule files
    builder.add_rule_files([
        '/etc/prometheus/rules/*.yml'
    ])
    
    return builder.build()


def create_recording_rules() -> Dict[str, Any]:
    """Create recording rules for performance optimization."""
    return {
        'groups': [
            {
                'name': 'llmoptimizer_aggregations',
                'interval': '30s',
                'rules': [
                    {
                        'record': 'instance:llmoptimizer_http_requests:rate5m',
                        'expr': 'rate(llmoptimizer_http_requests_total[5m])'
                    },
                    {
                        'record': 'instance:llmoptimizer_http_request_duration:mean5m',
                        'expr': 'rate(llmoptimizer_http_request_duration_seconds_sum[5m]) / rate(llmoptimizer_http_request_duration_seconds_count[5m])'
                    },
                    {
                        'record': 'instance:llmoptimizer_cache_hit_rate:mean5m',
                        'expr': 'rate(llmoptimizer_cache_hits_total[5m]) / (rate(llmoptimizer_cache_hits_total[5m]) + rate(llmoptimizer_cache_misses_total[5m]))'
                    },
                    {
                        'record': 'instance:llmoptimizer_error_rate:mean5m',
                        'expr': 'rate(llmoptimizer_errors_total[5m])'
                    },
                    {
                        'record': 'instance:llmoptimizer_llm_request_rate:mean5m',
                        'expr': 'rate(llmoptimizer_llm_requests_total[5m])'
                    }
                ]
            }
        ]
    }