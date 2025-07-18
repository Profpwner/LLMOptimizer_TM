"""
Grafana dashboard generator for LLMOptimizer monitoring.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import uuid


@dataclass
class Panel:
    """Grafana panel configuration."""
    title: str
    type: str  # graph, stat, gauge, table, etc.
    gridPos: Dict[str, int]
    datasource: str = "Prometheus"
    targets: List[Dict[str, Any]] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    fieldConfig: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = hash(self.title) % 1000


class GrafanaDashboardBuilder:
    """Builder for Grafana dashboards optimized for 100K+ users monitoring."""
    
    def __init__(self):
        self.dashboard_base = {
            "annotations": {
                "list": [
                    {
                        "builtIn": 1,
                        "datasource": "-- Grafana --",
                        "enable": True,
                        "hide": True,
                        "iconColor": "rgba(0, 211, 255, 1)",
                        "name": "Annotations & Alerts",
                        "type": "dashboard"
                    }
                ]
            },
            "editable": True,
            "gnetId": None,
            "graphTooltip": 0,
            "links": [],
            "liveNow": True,
            "panels": [],
            "refresh": "10s",
            "schemaVersion": 30,
            "style": "dark",
            "tags": [],
            "templating": {
                "list": []
            },
            "time": {
                "from": "now-1h",
                "to": "now"
            },
            "timepicker": {},
            "timezone": "",
            "version": 0
        }
    
    def create_system_overview_dashboard(self) -> Dict[str, Any]:
        """Create system overview dashboard."""
        dashboard = self.dashboard_base.copy()
        dashboard["title"] = "LLMOptimizer System Overview"
        dashboard["uid"] = "llm-system-overview"
        dashboard["tags"] = ["system", "overview"]
        
        panels = [
            # Request Rate
            Panel(
                title="Request Rate",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 0},
                targets=[{
                    "expr": 'sum(rate(http_requests_total{job="api-gateway"}[5m])) by (service)',
                    "legendFormat": "{{service}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "reqps",
                        "custom": {
                            "lineInterpolation": "smooth",
                            "showPoints": "never"
                        }
                    }
                }
            ),
            
            # Error Rate
            Panel(
                title="Error Rate",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 12, "y": 0},
                targets=[{
                    "expr": 'sum(rate(http_requests_total{job="api-gateway",status=~"5.."}[5m])) by (service)',
                    "legendFormat": "{{service}} 5xx",
                    "refId": "A"
                }, {
                    "expr": 'sum(rate(http_requests_total{job="api-gateway",status=~"4.."}[5m])) by (service)',
                    "legendFormat": "{{service}} 4xx",
                    "refId": "B"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "reqps",
                        "custom": {
                            "lineInterpolation": "smooth",
                            "showPoints": "never"
                        }
                    }
                }
            ),
            
            # Response Time P95
            Panel(
                title="Response Time (P95)",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 8},
                targets=[{
                    "expr": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="api-gateway"}[5m])) by (service, le))',
                    "legendFormat": "{{service}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "s",
                        "custom": {
                            "lineInterpolation": "smooth",
                            "showPoints": "never"
                        }
                    }
                }
            ),
            
            # Active Users
            Panel(
                title="Active Users",
                type="stat",
                gridPos={"h": 8, "w": 6, "x": 12, "y": 8},
                targets=[{
                    "expr": 'sum(increase(auth_active_users_total[5m]))',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 50000},
                                {"color": "red", "value": 80000}
                            ]
                        }
                    }
                }
            ),
            
            # CPU Usage
            Panel(
                title="CPU Usage",
                type="gauge",
                gridPos={"h": 8, "w": 6, "x": 18, "y": 8},
                targets=[{
                    "expr": 'avg(100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 70},
                                {"color": "red", "value": 90}
                            ]
                        }
                    }
                }
            ),
            
            # Memory Usage
            Panel(
                title="Memory Usage",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 16},
                targets=[{
                    "expr": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
                    "legendFormat": "{{instance}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100,
                        "custom": {
                            "lineInterpolation": "smooth",
                            "showPoints": "never"
                        }
                    }
                }
            ),
            
            # Database Connections
            Panel(
                title="Database Connections",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 12, "y": 16},
                targets=[{
                    "expr": 'pgbouncer_pools_client_active{database="llmoptimizer_main"}',
                    "legendFormat": "Active",
                    "refId": "A"
                }, {
                    "expr": 'pgbouncer_pools_client_waiting{database="llmoptimizer_main"}',
                    "legendFormat": "Waiting",
                    "refId": "B"
                }, {
                    "expr": 'pgbouncer_pools_client_idle{database="llmoptimizer_main"}',
                    "legendFormat": "Idle",
                    "refId": "C"
                }]
            )
        ]
        
        dashboard["panels"] = [panel.__dict__ for panel in panels]
        return dashboard
    
    def create_performance_dashboard(self) -> Dict[str, Any]:
        """Create performance monitoring dashboard."""
        dashboard = self.dashboard_base.copy()
        dashboard["title"] = "LLMOptimizer Performance Metrics"
        dashboard["uid"] = "llm-performance"
        dashboard["tags"] = ["performance", "sla"]
        
        panels = [
            # SLA Status
            Panel(
                title="SLA Status (99.9%)",
                type="stat",
                gridPos={"h": 4, "w": 6, "x": 0, "y": 0},
                targets=[{
                    "expr": '(1 - (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))) * 100',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 99.5},
                                {"color": "green", "value": 99.9}
                            ]
                        }
                    }
                }
            ),
            
            # Request Latency Distribution
            Panel(
                title="Request Latency Distribution",
                type="heatmap",
                gridPos={"h": 8, "w": 12, "x": 6, "y": 0},
                targets=[{
                    "expr": 'sum(rate(http_request_duration_seconds_bucket[5m])) by (le)',
                    "format": "heatmap",
                    "refId": "A"
                }],
                options={
                    "calculate": False,
                    "yAxis": {
                        "unit": "s",
                        "decimals": 0
                    }
                }
            ),
            
            # Throughput by Service
            Panel(
                title="Throughput by Service",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 8},
                targets=[{
                    "expr": 'sum(rate(http_requests_total[5m])) by (service)',
                    "legendFormat": "{{service}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "reqps"
                    }
                }
            ),
            
            # Cache Hit Rate
            Panel(
                title="Cache Hit Rate",
                type="gauge",
                gridPos={"h": 8, "w": 6, "x": 12, "y": 8},
                targets=[{
                    "expr": '(sum(rate(redis_keyspace_hits_total[5m])) / (sum(rate(redis_keyspace_hits_total[5m])) + sum(rate(redis_keyspace_misses_total[5m])))) * 100',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 80},
                                {"color": "green", "value": 95}
                            ]
                        }
                    }
                }
            ),
            
            # Database Query Time
            Panel(
                title="Database Query Time",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 16},
                targets=[{
                    "expr": 'histogram_quantile(0.95, sum(rate(pgbouncer_query_duration_seconds_bucket[5m])) by (le))',
                    "legendFormat": "P95",
                    "refId": "A"
                }, {
                    "expr": 'histogram_quantile(0.99, sum(rate(pgbouncer_query_duration_seconds_bucket[5m])) by (le))',
                    "legendFormat": "P99",
                    "refId": "B"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "s"
                    }
                }
            )
        ]
        
        dashboard["panels"] = [panel.__dict__ for panel in panels]
        return dashboard
    
    def create_llm_monitoring_dashboard(self) -> Dict[str, Any]:
        """Create LLM-specific monitoring dashboard."""
        dashboard = self.dashboard_base.copy()
        dashboard["title"] = "LLM Platform Monitoring"
        dashboard["uid"] = "llm-platform"
        dashboard["tags"] = ["llm", "ai", "monitoring"]
        
        panels = [
            # LLM API Request Rate
            Panel(
                title="LLM API Request Rate",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 0},
                targets=[{
                    "expr": 'sum(rate(llm_api_requests_total[5m])) by (provider)',
                    "legendFormat": "{{provider}}",
                    "refId": "A"
                }]
            ),
            
            # LLM API Error Rate
            Panel(
                title="LLM API Error Rate",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 12, "y": 0},
                targets=[{
                    "expr": 'sum(rate(llm_api_errors_total[5m])) by (provider, error_type)',
                    "legendFormat": "{{provider}} - {{error_type}}",
                    "refId": "A"
                }]
            ),
            
            # Token Usage
            Panel(
                title="Token Usage Rate",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 8},
                targets=[{
                    "expr": 'sum(rate(llm_tokens_used_total[5m])) by (provider, type)',
                    "legendFormat": "{{provider}} - {{type}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "short"
                    }
                }
            ),
            
            # LLM Response Time
            Panel(
                title="LLM Response Time",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 12, "y": 8},
                targets=[{
                    "expr": 'histogram_quantile(0.95, sum(rate(llm_response_duration_seconds_bucket[5m])) by (provider, le))',
                    "legendFormat": "{{provider}} P95",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "s"
                    }
                }
            ),
            
            # Brand Visibility Score
            Panel(
                title="Brand Visibility Score",
                type="gauge",
                gridPos={"h": 8, "w": 8, "x": 0, "y": 16},
                targets=[{
                    "expr": 'avg(brand_visibility_score)',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 50},
                                {"color": "green", "value": 75}
                            ]
                        }
                    }
                }
            ),
            
            # Semantic Analysis Queue
            Panel(
                title="Semantic Analysis Queue",
                type="stat",
                gridPos={"h": 8, "w": 8, "x": 8, "y": 16},
                targets=[{
                    "expr": 'semantic_analysis_queue_size',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 1000},
                                {"color": "red", "value": 5000}
                            ]
                        }
                    }
                }
            ),
            
            # Content Optimization Rate
            Panel(
                title="Content Optimization Rate",
                type="stat",
                gridPos={"h": 8, "w": 8, "x": 16, "y": 16},
                targets=[{
                    "expr": 'sum(rate(content_optimizations_total[5m])) * 60',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "decimals": 0
                    }
                },
                options={
                    "reduceOptions": {
                        "calcs": ["lastNotNull"]
                    },
                    "textMode": "auto"
                }
            )
        ]
        
        dashboard["panels"] = [panel.__dict__ for panel in panels]
        return dashboard
    
    def create_infrastructure_dashboard(self) -> Dict[str, Any]:
        """Create infrastructure monitoring dashboard."""
        dashboard = self.dashboard_base.copy()
        dashboard["title"] = "Infrastructure Health"
        dashboard["uid"] = "llm-infrastructure"
        dashboard["tags"] = ["infrastructure", "kubernetes"]
        
        panels = [
            # Kubernetes Pod Status
            Panel(
                title="Pod Status",
                type="stat",
                gridPos={"h": 6, "w": 6, "x": 0, "y": 0},
                targets=[{
                    "expr": 'sum(kube_pod_status_phase{namespace="llmoptimizer",phase="Running"})',
                    "legendFormat": "Running",
                    "refId": "A"
                }, {
                    "expr": 'sum(kube_pod_status_phase{namespace="llmoptimizer",phase!="Running"})',
                    "legendFormat": "Not Running",
                    "refId": "B"
                }]
            ),
            
            # Node CPU Usage
            Panel(
                title="Node CPU Usage",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 6, "y": 0},
                targets=[{
                    "expr": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
                    "legendFormat": "{{instance}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100
                    }
                }
            ),
            
            # Node Memory Usage
            Panel(
                title="Node Memory Usage",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 8},
                targets=[{
                    "expr": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
                    "legendFormat": "{{instance}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100
                    }
                }
            ),
            
            # Disk Usage
            Panel(
                title="Disk Usage",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 12, "y": 8},
                targets=[{
                    "expr": '100 - ((node_filesystem_avail_bytes{mountpoint="/",fstype!="rootfs"} * 100) / node_filesystem_size_bytes{mountpoint="/",fstype!="rootfs"})',
                    "legendFormat": "{{instance}}",
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "max": 100
                    }
                }
            ),
            
            # Network I/O
            Panel(
                title="Network I/O",
                type="graph",
                gridPos={"h": 8, "w": 12, "x": 0, "y": 16},
                targets=[{
                    "expr": 'sum(rate(node_network_receive_bytes_total[5m])) by (instance)',
                    "legendFormat": "{{instance}} RX",
                    "refId": "A"
                }, {
                    "expr": 'sum(rate(node_network_transmit_bytes_total[5m])) by (instance)',
                    "legendFormat": "{{instance}} TX",
                    "refId": "B"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "Bps"
                    }
                }
            ),
            
            # Container Restarts
            Panel(
                title="Container Restarts (24h)",
                type="stat",
                gridPos={"h": 8, "w": 6, "x": 12, "y": 16},
                targets=[{
                    "expr": 'sum(increase(kube_pod_container_status_restarts_total{namespace="llmoptimizer"}[24h]))',
                    "refId": "A"
                }],
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 10},
                                {"color": "red", "value": 50}
                            ]
                        }
                    }
                }
            ),
            
            # PVC Usage
            Panel(
                title="Persistent Volume Usage",
                type="table",
                gridPos={"h": 8, "w": 6, "x": 18, "y": 16},
                targets=[{
                    "expr": '100 * kubelet_volume_stats_used_bytes{namespace="llmoptimizer"} / kubelet_volume_stats_capacity_bytes{namespace="llmoptimizer"}',
                    "format": "table",
                    "instant": True,
                    "refId": "A"
                }]
            )
        ]
        
        dashboard["panels"] = [panel.__dict__ for panel in panels]
        return dashboard
    
    def export_dashboards(self, output_dir: str = "dashboards"):
        """Export all dashboards to JSON files."""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        dashboards = {
            "system-overview": self.create_system_overview_dashboard(),
            "performance": self.create_performance_dashboard(),
            "llm-monitoring": self.create_llm_monitoring_dashboard(),
            "infrastructure": self.create_infrastructure_dashboard()
        }
        
        for name, dashboard in dashboards.items():
            with open(os.path.join(output_dir, f"{name}.json"), 'w') as f:
                json.dump(dashboard, f, indent=2)
        
        return dashboards


# Custom metrics for LLMOptimizer
class LLMOptimizerMetrics:
    """Custom metrics for LLMOptimizer application."""
    
    def __init__(self, registry=None):
        self.registry = registry or CollectorRegistry()
        
        # HTTP metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status', 'service'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint', 'service'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry
        )
        
        # LLM metrics
        self.llm_api_requests_total = Counter(
            'llm_api_requests_total',
            'Total LLM API requests',
            ['provider', 'model', 'operation'],
            registry=self.registry
        )
        
        self.llm_api_errors_total = Counter(
            'llm_api_errors_total',
            'Total LLM API errors',
            ['provider', 'model', 'error_type'],
            registry=self.registry
        )
        
        self.llm_tokens_used_total = Counter(
            'llm_tokens_used_total',
            'Total tokens used',
            ['provider', 'model', 'type'],  # type: prompt/completion
            registry=self.registry
        )
        
        self.llm_response_duration_seconds = Histogram(
            'llm_response_duration_seconds',
            'LLM API response time',
            ['provider', 'model'],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
            registry=self.registry
        )
        
        # Business metrics
        self.brand_visibility_score = Gauge(
            'brand_visibility_score',
            'Current brand visibility score',
            ['brand', 'platform'],
            registry=self.registry
        )
        
        self.content_optimizations_total = Counter(
            'content_optimizations_total',
            'Total content optimizations performed',
            ['type', 'status'],
            registry=self.registry
        )
        
        self.semantic_analysis_queue_size = Gauge(
            'semantic_analysis_queue_size',
            'Current semantic analysis queue size',
            registry=self.registry
        )
        
        # Authentication metrics
        self.auth_active_users_total = Gauge(
            'auth_active_users_total',
            'Total active users',
            ['auth_type'],
            registry=self.registry
        )
        
        self.auth_login_attempts_total = Counter(
            'auth_login_attempts_total',
            'Total login attempts',
            ['method', 'status'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_operations_total = Counter(
            'cache_operations_total',
            'Total cache operations',
            ['operation', 'cache_type'],
            registry=self.registry
        )
        
        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio',
            ['cache_type'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_connections_active = Gauge(
            'db_connections_active',
            'Active database connections',
            ['database', 'pool'],
            registry=self.registry
        )
        
        self.db_query_duration_seconds = Histogram(
            'db_query_duration_seconds',
            'Database query duration',
            ['database', 'operation'],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
            registry=self.registry
        )
    
    def start_metrics_server(self, port: int = 8000):
        """Start Prometheus metrics server."""
        start_http_server(port, registry=self.registry)
        logger.info(f"Metrics server started on port {port}")
    
    def push_to_gateway(self, gateway_url: str, job: str = 'llmoptimizer'):
        """Push metrics to Prometheus Pushgateway."""
        push_to_gateway(gateway_url, job=job, registry=self.registry)


if __name__ == "__main__":
    # Generate and export dashboards
    builder = GrafanaDashboardBuilder()
    builder.export_dashboards("/etc/grafana/dashboards")