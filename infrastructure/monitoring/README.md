# LLMOptimizer Monitoring Stack

This directory contains the complete monitoring stack for the LLMOptimizer platform, including Prometheus, Grafana, Jaeger, and the ELK stack.

## Components

### 1. Prometheus Stack (`prometheus/`)
- **Prometheus Server**: Metrics collection and storage
- **Prometheus Operator**: Kubernetes-native deployment and management
- **Service Monitors**: Auto-discovery of services to monitor
- **Recording Rules**: Pre-computed metrics for performance
- **Alert Rules**: Proactive alerting on service health

### 2. Grafana (`grafana/`)
- **Grafana Server**: Visualization and dashboarding
- **Pre-configured Dashboards**:
  - Service Overview
  - ML Service Performance
  - Content Service Analytics
  - Security Monitoring
  - Infrastructure Overview
- **Multiple Datasources**: Prometheus, Jaeger, Elasticsearch, Loki

### 3. Jaeger (`jaeger/`)
- **Distributed Tracing**: End-to-end request tracing
- **Jaeger Operator**: Automated deployment and scaling
- **OpenTelemetry Collector**: Enhanced trace collection and processing
- **Sampling Strategies**: Adaptive sampling for production

### 4. ELK Stack (`elk/`)
- **Elasticsearch**: Log storage and search
- **Logstash**: Log processing and enrichment
- **Kibana**: Log visualization and analysis
- **Filebeat**: Log collection from containers

## Deployment

### Prerequisites
1. Kubernetes cluster with Istio installed
2. Persistent storage classes configured
3. TLS certificates generated

### Installation Steps

1. **Deploy Prometheus Stack**:
```bash
kubectl apply -f prometheus/prometheus-operator.yaml
kubectl apply -f prometheus/service-monitors.yaml
kubectl apply -f prometheus/recording-rules.yaml
kubectl apply -f prometheus/alert-rules.yaml
```

2. **Deploy Grafana**:
```bash
kubectl apply -f grafana/grafana-deployment.yaml
kubectl apply -f grafana/datasources.yaml
kubectl apply -f grafana/dashboards.yaml
```

3. **Deploy Jaeger**:
```bash
kubectl apply -f jaeger/jaeger-operator.yaml
kubectl apply -f jaeger/jaeger-instance.yaml
kubectl apply -f jaeger/opentelemetry-collector.yaml
```

4. **Deploy ELK Stack**:
```bash
kubectl apply -f elk/elasticsearch.yaml
kubectl apply -f elk/logstash.yaml
kubectl apply -f elk/kibana.yaml
```

## Configuration

### Prometheus
- Retention: 30 days
- Storage: 100GB per replica
- Scrape interval: 30s (default), 15s (critical services)

### Grafana
- Admin credentials: Stored in `grafana-secrets`
- OAuth integration: Configured for LLMOptimizer auth
- Dashboards: Auto-provisioned from ConfigMaps

### Jaeger
- Storage: Elasticsearch backend
- Retention: 7 days
- Sampling: Adaptive (1% default, 10% for ML service)

### ELK Stack
- Index Lifecycle: Hot (1d) → Warm (2d) → Cold (7d) → Delete (30d)
- Shards: 3 primary, 1 replica
- Log parsing: JSON, Kubernetes metadata, Istio access logs

## Access

### Internal Access
- Prometheus: `http://prometheus.monitoring:9090`
- Grafana: `http://grafana.monitoring:3000`
- Jaeger: `http://jaeger-query.monitoring:16686`
- Kibana: `http://kibana.monitoring:5601`

### External Access (via Istio Gateway)
- Grafana: `https://grafana.llmoptimizer.com`
- Prometheus: `https://prometheus.llmoptimizer.com`
- Jaeger: `https://jaeger.llmoptimizer.com`
- Kibana: `https://kibana.llmoptimizer.com`

## Monitoring Workflows

### Service Health Monitoring
1. Check Grafana Service Overview dashboard
2. Review error rates and latencies
3. Drill down to specific service dashboards
4. Correlate with traces in Jaeger

### Log Analysis
1. Access Kibana
2. Use index patterns: `logs-*`, `istio-access-*`, `app-*`
3. Filter by service, level, or time range
4. Create visualizations for recurring patterns

### Distributed Tracing
1. Access Jaeger UI
2. Search traces by service, operation, or tags
3. Analyze latency breakdowns
4. Identify bottlenecks and errors

### Alert Management
1. Alerts fire to AlertManager
2. Notifications sent via configured channels
3. Acknowledge in Grafana or AlertManager UI
4. Follow runbooks for resolution

## Maintenance

### Backup
- Elasticsearch snapshots: Daily to S3
- Prometheus snapshots: Every 6 hours
- Grafana database: Daily PostgreSQL backup

### Scaling
- Prometheus: Scale replicas based on metrics volume
- Elasticsearch: Add nodes for storage/performance
- Logstash: Scale workers based on log volume
- Jaeger Collector: Auto-scaling enabled

### Updates
1. Update image versions in deployments
2. Apply CRD updates if needed
3. Rolling updates with zero downtime
4. Test in staging environment first

## Troubleshooting

### High Memory Usage
- Check Prometheus cardinality
- Review Elasticsearch heap settings
- Adjust resource limits

### Missing Metrics
- Verify ServiceMonitor labels
- Check network policies
- Review Prometheus targets

### Slow Queries
- Optimize Elasticsearch indices
- Add recording rules for common queries
- Scale infrastructure if needed

### Log Ingestion Issues
- Check Filebeat DaemonSet status
- Verify Logstash pipeline health
- Review Elasticsearch cluster health

## Security Considerations

1. **TLS Everywhere**: All components use TLS
2. **Authentication**: Integrated with LLMOptimizer auth
3. **RBAC**: Least privilege access
4. **Network Policies**: Restricted inter-service communication
5. **Secrets Management**: Kubernetes secrets with encryption

## Performance Optimization

1. **Index Optimization**: Time-based indices with ILM
2. **Query Optimization**: Recording rules and materialized views
3. **Sampling**: Adaptive sampling for traces
4. **Caching**: Redis cache for frequently accessed data
5. **Resource Allocation**: Based on production workloads

## Integration Points

1. **Application Metrics**: Prometheus client libraries
2. **Tracing**: OpenTelemetry SDKs
3. **Logging**: Structured JSON logging
4. **Alerting**: Webhook integrations
5. **Dashboards**: Embedded Grafana panels