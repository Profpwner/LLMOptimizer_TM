"""
SLO/SLA monitoring configuration for LLMOptimizer.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import yaml
import json


class SLOType(Enum):
    """Types of SLO measurements."""
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    QUALITY = "quality"


@dataclass
class SLOTarget:
    """SLO target definition."""
    name: str
    type: SLOType
    target: float  # Target percentage or value
    window: str  # Time window (e.g., "30d", "7d", "1h")
    description: str
    query: str  # Prometheus query
    unit: str = "percent"
    critical_threshold: Optional[float] = None
    warning_threshold: Optional[float] = None
    
    def to_prometheus_rule(self) -> Dict[str, Any]:
        """Convert to Prometheus recording rule."""
        return {
            "record": f"slo:{self.name}:{self.window}",
            "expr": self.query,
            "labels": {
                "slo_name": self.name,
                "slo_type": self.type.value,
                "slo_target": str(self.target),
                "slo_window": self.window
            }
        }


@dataclass
class SLADefinition:
    """SLA definition with multiple SLOs."""
    name: str
    description: str
    tier: str  # e.g., "enterprise", "standard", "free"
    slos: List[SLOTarget] = field(default_factory=list)
    escalation_policy: Dict[str, Any] = field(default_factory=dict)
    reporting_frequency: str = "monthly"
    penalties: Dict[str, Any] = field(default_factory=dict)


class SLOManager:
    """Manager for SLO/SLA definitions and monitoring."""
    
    def __init__(self):
        self.slos = self._define_slos()
        self.slas = self._define_slas()
    
    def _define_slos(self) -> List[SLOTarget]:
        """Define all SLO targets."""
        return [
            # Availability SLOs
            SLOTarget(
                name="api_availability",
                type=SLOType.AVAILABILITY,
                target=99.9,
                window="30d",
                description="API availability excluding planned maintenance",
                query="""
                    (1 - (
                        sum(increase(http_requests_total{status=~"5.."}[30d]))
                        /
                        sum(increase(http_requests_total[30d]))
                    )) * 100
                """,
                critical_threshold=99.5,
                warning_threshold=99.7
            ),
            SLOTarget(
                name="api_availability_7d",
                type=SLOType.AVAILABILITY,
                target=99.95,
                window="7d",
                description="API availability over 7 days",
                query="""
                    (1 - (
                        sum(increase(http_requests_total{status=~"5.."}[7d]))
                        /
                        sum(increase(http_requests_total[7d]))
                    )) * 100
                """,
                critical_threshold=99.9,
                warning_threshold=99.93
            ),
            
            # Latency SLOs
            SLOTarget(
                name="api_latency_p95",
                type=SLOType.LATENCY,
                target=0.5,  # 500ms
                window="1h",
                description="95th percentile API latency",
                query="""
                    histogram_quantile(0.95,
                        sum(rate(http_request_duration_seconds_bucket[1h])) by (le)
                    )
                """,
                unit="seconds",
                critical_threshold=1.0,
                warning_threshold=0.75
            ),
            SLOTarget(
                name="api_latency_p99",
                type=SLOType.LATENCY,
                target=2.0,  # 2s
                window="1h",
                description="99th percentile API latency",
                query="""
                    histogram_quantile(0.99,
                        sum(rate(http_request_duration_seconds_bucket[1h])) by (le)
                    )
                """,
                unit="seconds",
                critical_threshold=5.0,
                warning_threshold=3.0
            ),
            
            # LLM-specific SLOs
            SLOTarget(
                name="llm_availability",
                type=SLOType.AVAILABILITY,
                target=99.5,
                window="24h",
                description="LLM API availability",
                query="""
                    (1 - (
                        sum(increase(llm_api_errors_total[24h]))
                        /
                        sum(increase(llm_api_requests_total[24h]))
                    )) * 100
                """,
                critical_threshold=99.0,
                warning_threshold=99.3
            ),
            SLOTarget(
                name="llm_response_time_p95",
                type=SLOType.LATENCY,
                target=10.0,  # 10s
                window="1h",
                description="95th percentile LLM response time",
                query="""
                    histogram_quantile(0.95,
                        sum(rate(llm_response_duration_seconds_bucket[1h])) by (le)
                    )
                """,
                unit="seconds",
                critical_threshold=30.0,
                warning_threshold=20.0
            ),
            
            # Content optimization SLOs
            SLOTarget(
                name="content_optimization_success_rate",
                type=SLOType.QUALITY,
                target=95.0,
                window="24h",
                description="Content optimization success rate",
                query="""
                    (
                        sum(increase(content_optimizations_total{status="success"}[24h]))
                        /
                        sum(increase(content_optimizations_total[24h]))
                    ) * 100
                """,
                critical_threshold=90.0,
                warning_threshold=93.0
            ),
            SLOTarget(
                name="semantic_analysis_throughput",
                type=SLOType.THROUGHPUT,
                target=1000,  # analyses per hour
                window="1h",
                description="Semantic analysis throughput",
                query="""
                    sum(rate(semantic_analysis_completed_total[1h])) * 3600
                """,
                unit="per_hour",
                critical_threshold=500,
                warning_threshold=750
            ),
            
            # Database SLOs
            SLOTarget(
                name="database_query_latency_p95",
                type=SLOType.LATENCY,
                target=0.1,  # 100ms
                window="5m",
                description="95th percentile database query latency",
                query="""
                    histogram_quantile(0.95,
                        sum(rate(db_query_duration_seconds_bucket[5m])) by (le)
                    )
                """,
                unit="seconds",
                critical_threshold=0.5,
                warning_threshold=0.25
            ),
            
            # Cache SLOs
            SLOTarget(
                name="cache_hit_rate",
                type=SLOType.QUALITY,
                target=95.0,
                window="1h",
                description="Cache hit rate",
                query="""
                    (
                        sum(rate(redis_keyspace_hits_total[1h]))
                        /
                        (sum(rate(redis_keyspace_hits_total[1h])) + sum(rate(redis_keyspace_misses_total[1h])))
                    ) * 100
                """,
                critical_threshold=85.0,
                warning_threshold=90.0
            ),
            
            # Error budget SLO
            SLOTarget(
                name="error_budget_remaining",
                type=SLOType.QUALITY,
                target=100.0,
                window="30d",
                description="Remaining error budget",
                query="""
                    100 - (
                        (
                            sum(increase(http_requests_total{status=~"5.."}[30d]))
                            /
                            sum(increase(http_requests_total[30d]))
                        ) * 100 / 0.1
                    )
                """,
                critical_threshold=10.0,
                warning_threshold=25.0
            )
        ]
    
    def _define_slas(self) -> Dict[str, SLADefinition]:
        """Define SLAs for different service tiers."""
        return {
            "enterprise": SLADefinition(
                name="Enterprise SLA",
                description="Premium service level agreement for enterprise customers",
                tier="enterprise",
                slos=[
                    slo for slo in self.slos if slo.name in [
                        "api_availability",
                        "api_latency_p95",
                        "api_latency_p99",
                        "llm_availability",
                        "content_optimization_success_rate",
                        "database_query_latency_p95"
                    ]
                ],
                escalation_policy={
                    "levels": [
                        {
                            "level": 1,
                            "contacts": ["oncall-primary"],
                            "delay": "0m"
                        },
                        {
                            "level": 2,
                            "contacts": ["team-lead", "oncall-secondary"],
                            "delay": "15m"
                        },
                        {
                            "level": 3,
                            "contacts": ["engineering-manager", "cto"],
                            "delay": "30m"
                        }
                    ]
                },
                reporting_frequency="weekly",
                penalties={
                    "availability_breach": {
                        "99.9_to_99.5": "5% monthly credit",
                        "99.5_to_99.0": "10% monthly credit",
                        "below_99.0": "25% monthly credit"
                    },
                    "latency_breach": {
                        "minor": "2% monthly credit per hour",
                        "major": "5% monthly credit per hour"
                    }
                }
            ),
            "standard": SLADefinition(
                name="Standard SLA",
                description="Standard service level agreement",
                tier="standard",
                slos=[
                    slo for slo in self.slos if slo.name in [
                        "api_availability_7d",
                        "api_latency_p95",
                        "llm_availability",
                        "content_optimization_success_rate"
                    ]
                ],
                escalation_policy={
                    "levels": [
                        {
                            "level": 1,
                            "contacts": ["oncall-primary"],
                            "delay": "0m"
                        },
                        {
                            "level": 2,
                            "contacts": ["team-lead"],
                            "delay": "30m"
                        }
                    ]
                },
                reporting_frequency="monthly",
                penalties={
                    "availability_breach": {
                        "99.5_to_99.0": "5% monthly credit",
                        "below_99.0": "10% monthly credit"
                    }
                }
            ),
            "free": SLADefinition(
                name="Free Tier SLA",
                description="Best-effort service level",
                tier="free",
                slos=[
                    slo for slo in self.slos if slo.name in [
                        "api_availability_7d"
                    ]
                ],
                escalation_policy={
                    "levels": [
                        {
                            "level": 1,
                            "contacts": ["support-queue"],
                            "delay": "0m"
                        }
                    ]
                },
                reporting_frequency="quarterly",
                penalties={}
            )
        }
    
    def generate_prometheus_rules(self) -> Dict[str, Any]:
        """Generate Prometheus recording and alerting rules for SLOs."""
        recording_rules = []
        alerting_rules = []
        
        for slo in self.slos:
            # Recording rule for SLO
            recording_rules.append(slo.to_prometheus_rule())
            
            # Alerting rules for SLO breaches
            if slo.critical_threshold:
                alerting_rules.append({
                    "alert": f"SLOBreach_{slo.name}_critical",
                    "expr": f"slo:{slo.name}:{slo.window} < {slo.critical_threshold}",
                    "for": "5m",
                    "labels": {
                        "severity": "critical",
                        "slo_name": slo.name,
                        "team": "platform"
                    },
                    "annotations": {
                        "summary": f"Critical SLO breach: {slo.name}",
                        "description": f"{slo.description} is {{{{ $value | humanize }}}} (target: {slo.target}{slo.unit})"
                    }
                })
            
            if slo.warning_threshold:
                alerting_rules.append({
                    "alert": f"SLOBreach_{slo.name}_warning",
                    "expr": f"slo:{slo.name}:{slo.window} < {slo.warning_threshold}",
                    "for": "10m",
                    "labels": {
                        "severity": "warning",
                        "slo_name": slo.name,
                        "team": "platform"
                    },
                    "annotations": {
                        "summary": f"Warning SLO breach: {slo.name}",
                        "description": f"{slo.description} is {{{{ $value | humanize }}}} (target: {slo.target}{slo.unit})"
                    }
                })
        
        # Error budget burn rate alerts
        alerting_rules.extend([
            {
                "alert": "ErrorBudgetBurnRateHigh",
                "expr": """
                    (
                        sum(rate(http_requests_total{status=~"5.."}[1h]))
                        /
                        sum(rate(http_requests_total[1h]))
                    ) > 0.01
                """,
                "for": "5m",
                "labels": {
                    "severity": "warning",
                    "team": "platform"
                },
                "annotations": {
                    "summary": "High error budget burn rate",
                    "description": "Error rate is {{ $value | humanizePercentage }} over the last hour"
                }
            },
            {
                "alert": "ErrorBudgetExhausted",
                "expr": "slo:error_budget_remaining:30d < 10",
                "for": "5m",
                "labels": {
                    "severity": "critical",
                    "team": "platform",
                    "pagerduty": "true"
                },
                "annotations": {
                    "summary": "Error budget nearly exhausted",
                    "description": "Only {{ $value | humanize }}% of error budget remains"
                }
            }
        ])
        
        return {
            "groups": [
                {
                    "name": "slo_recording_rules",
                    "interval": "30s",
                    "rules": recording_rules
                },
                {
                    "name": "slo_alerting_rules",
                    "interval": "30s",
                    "rules": alerting_rules
                }
            ]
        }
    
    def generate_grafana_dashboard(self) -> Dict[str, Any]:
        """Generate Grafana dashboard for SLO monitoring."""
        panels = []
        y_pos = 0
        
        # Overview section
        panels.extend([
            {
                "title": "SLO Compliance Overview",
                "type": "stat",
                "gridPos": {"h": 4, "w": 24, "x": 0, "y": y_pos},
                "targets": [
                    {
                        "expr": f'slo:{slo.name}:{slo.window}',
                        "legendFormat": slo.name.replace("_", " ").title(),
                        "refId": chr(65 + i)
                    }
                    for i, slo in enumerate(self.slos[:6])
                ]
            }
        ])
        y_pos += 4
        
        # Detailed SLO panels
        for slo in self.slos:
            panels.append({
                "title": f"{slo.name.replace('_', ' ').title()} ({slo.window})",
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": (len(panels) % 2) * 12, "y": y_pos},
                "targets": [{
                    "expr": f'slo:{slo.name}:{slo.window}',
                    "refId": "A"
                }],
                "yaxes": [{
                    "format": slo.unit,
                    "label": slo.description
                }],
                "thresholds": [
                    {"value": slo.critical_threshold, "color": "red", "fill": True} if slo.critical_threshold else None,
                    {"value": slo.warning_threshold, "color": "yellow", "fill": True} if slo.warning_threshold else None,
                    {"value": slo.target, "color": "green", "fill": False}
                ]
            })
            
            if (len(panels) - 1) % 2 == 1:
                y_pos += 8
        
        return {
            "title": "SLO/SLA Monitoring",
            "uid": "slo-monitoring",
            "panels": panels,
            "refresh": "30s",
            "time": {"from": "now-24h", "to": "now"}
        }
    
    def export_configurations(self, output_dir: str = "/etc/prometheus/rules"):
        """Export all SLO/SLA configurations."""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Export Prometheus rules
        with open(os.path.join(output_dir, "slo_rules.yml"), 'w') as f:
            yaml.dump(self.generate_prometheus_rules(), f, default_flow_style=False)
        
        # Export SLA definitions
        sla_export = {
            tier: {
                "name": sla.name,
                "description": sla.description,
                "slos": [
                    {
                        "name": slo.name,
                        "target": slo.target,
                        "window": slo.window,
                        "description": slo.description
                    }
                    for slo in sla.slos
                ],
                "escalation_policy": sla.escalation_policy,
                "penalties": sla.penalties
            }
            for tier, sla in self.slas.items()
        }
        
        with open(os.path.join(output_dir, "sla_definitions.json"), 'w') as f:
            json.dump(sla_export, f, indent=2)
        
        # Export Grafana dashboard
        with open(os.path.join(output_dir, "slo_dashboard.json"), 'w') as f:
            json.dump(self.generate_grafana_dashboard(), f, indent=2)


if __name__ == "__main__":
    # Generate and export SLO/SLA configurations
    manager = SLOManager()
    manager.export_configurations()