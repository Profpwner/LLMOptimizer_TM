# LLMOptimizer Istio Service Mesh Configuration

This directory contains the Istio service mesh configuration for the LLMOptimizer platform, providing advanced traffic management, security, and observability features.

## Directory Structure

```
istio/
├── base/                    # Core Istio installation and configuration
│   ├── istio-operator.yaml # IstioOperator configuration
│   └── namespaces.yaml     # Namespace configuration with sidecar injection
├── gateways/               # Ingress and egress gateway configurations
│   └── main-gateway.yaml   # Gateway definitions for external traffic
├── security/               # Security policies and authentication
│   ├── mtls-policies.yaml  # mTLS configuration
│   ├── authorization-policies.yaml # RBAC policies
│   └── jwt-authentication.yaml # JWT validation for external traffic
├── traffic-management/     # Traffic routing and resilience
│   ├── virtual-services.yaml # Request routing rules
│   ├── destination-rules.yaml # Load balancing and circuit breakers
│   └── retry-timeout-policies.yaml # Retry and timeout configurations
├── telemetry/             # Observability configuration
│   └── telemetry-v2.yaml  # Metrics, tracing, and logging setup
└── install.sh            # Installation script
```

## Installation

### Prerequisites
- Kubernetes cluster (1.23+)
- kubectl configured
- Minimum 4 CPUs and 8GB RAM available

### Quick Start

```bash
# Run the installation script
./install.sh

# Verify installation
istioctl verify-install
kubectl get pods -n istio-system
```

### Manual Installation

1. **Install Istio Control Plane**:
```bash
istioctl install -f base/istio-operator.yaml -y
```

2. **Create Namespaces**:
```bash
kubectl apply -f base/namespaces.yaml
```

3. **Apply Security Policies**:
```bash
kubectl apply -f security/
```

4. **Configure Traffic Management**:
```bash
kubectl apply -f traffic-management/
```

5. **Set Up Telemetry**:
```bash
kubectl apply -f telemetry/
```

6. **Deploy Gateways**:
```bash
kubectl apply -f gateways/
```

## Key Features Configured

### 1. Security

#### mTLS (Mutual TLS)
- **Strict Mode**: Enforced for all services in the mesh
- **Automatic Certificate Rotation**: Managed by Istio
- **Permissive Mode**: For databases during migration

#### Authorization Policies
- **Default Deny**: All traffic blocked by default
- **Service-to-Service**: Explicit allow rules based on service accounts
- **JWT Validation**: For external API traffic
- **Rate Limiting**: Based on user tiers

### 2. Traffic Management

#### Load Balancing
- **Algorithms**: ROUND_ROBIN, LEAST_REQUEST, CONSISTENT_HASH
- **Session Affinity**: For content-service using session ID

#### Circuit Breakers
- **Consecutive Errors**: 5 errors trigger circuit breaker
- **Ejection Time**: 30 seconds base, exponential backoff
- **Max Ejection**: 50% of endpoints

#### Retry Policies
- **Retry Conditions**: 5xx, reset, connect-failure
- **Max Attempts**: 3 for most services, 1 for ML service
- **Timeout**: Per-service configuration (15s to 120s)

#### Canary Deployments
- **Content Service**: 95% stable, 5% canary
- **Header-Based Routing**: Force canary with `x-version: canary`

#### A/B Testing
- **ML Service**: 50/50 split between versions
- **User Group Routing**: Based on `x-user-group` header

### 3. Observability

#### Metrics
- **Prometheus Integration**: Automatic metrics collection
- **Custom Dimensions**: User tier, API version, model name
- **Recording Rules**: Pre-aggregated metrics

#### Tracing
- **Jaeger Integration**: Distributed tracing
- **Sampling**: 1% default, 10% for ML service
- **Trace Propagation**: B3 headers

#### Access Logs
- **Format**: Detailed with trace IDs
- **Destination**: stdout for collection by Filebeat

## Service Configuration

### API Gateway
- **Timeout**: 30s
- **Retries**: 3 attempts
- **Circuit Breaker**: 100 max connections

### Auth Service
- **Timeout**: 15s
- **Retries**: 2 attempts
- **Circuit Breaker**: 50 max connections

### Content Service
- **Timeout**: 60s
- **Retries**: 3 attempts
- **Canary Deployment**: Enabled
- **Session Affinity**: Based on x-session-id

### ML Service
- **Timeout**: 120s
- **Retries**: 1 attempt (idempotent operations only)
- **A/B Testing**: Enabled
- **Connection Pool**: 20 max connections

## External Service Access

Configured ServiceEntries for:
- OpenAI API
- Anthropic API
- Perplexity API
- Google APIs
- GitHub, Salesforce, HubSpot (integrations)

All external traffic goes through egress gateway with:
- Connection pooling
- Circuit breakers
- Retry policies
- Observability

## Monitoring and Dashboards

### Kiali
Access service mesh topology and health:
```bash
istioctl dashboard kiali
```

### Grafana
Pre-configured dashboards:
- Istio Control Plane
- Service Mesh Performance
- Request Flow
- mTLS Status

### Prometheus
Metrics available:
- Request rate, error rate, latency (RED metrics)
- Connection pool metrics
- Circuit breaker statistics
- mTLS handshake metrics

## Troubleshooting

### Common Issues

1. **503 Service Unavailable**
   - Check circuit breaker status
   - Verify destination rules
   - Check pod readiness

2. **401 Unauthorized**
   - Verify JWT token
   - Check authorization policies
   - Validate service account

3. **Connection Refused**
   - Verify mTLS configuration
   - Check network policies
   - Validate sidecar injection

### Debug Commands

```bash
# Check proxy configuration
istioctl proxy-config cluster <pod-name> -n <namespace>

# View proxy logs
kubectl logs <pod-name> -c istio-proxy -n <namespace>

# Analyze configuration
istioctl analyze -n <namespace>

# Check mTLS status
istioctl authn tls-check <pod-name> -n <namespace>
```

## Best Practices

1. **Gradual Rollout**: Use canary deployments for changes
2. **Observability First**: Monitor before making changes
3. **Security by Default**: Start with deny-all policies
4. **Resource Limits**: Set appropriate limits for sidecars
5. **Circuit Breakers**: Configure based on service SLAs

## Performance Tuning

### Sidecar Resources
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

### Concurrency
- Default: 2 worker threads
- Adjust based on workload

### Connection Pools
- Tuned per service requirements
- Monitor pool utilization

## Security Hardening

1. **Strict mTLS**: Enforced cluster-wide
2. **RBAC**: Fine-grained authorization
3. **JWT Validation**: External traffic authentication
4. **Network Policies**: Defense in depth
5. **Egress Control**: Explicit external access

## Upgrade Process

1. **Review Release Notes**: Check breaking changes
2. **Test in Staging**: Validate configuration
3. **Canary Upgrade**: Gradual rollout
4. **Monitor Metrics**: Watch for anomalies
5. **Rollback Plan**: Document and test

## Maintenance

### Certificate Rotation
- Automatic by Istio (every 24 hours)
- Root certificate: Manual rotation yearly

### Policy Updates
- Apply incrementally
- Test with dry-run mode
- Monitor authorization metrics

### Performance Reviews
- Monthly analysis of metrics
- Optimize based on usage patterns
- Adjust resource allocations