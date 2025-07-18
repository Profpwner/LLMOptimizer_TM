# Kubernetes Security and Compliance Framework

This directory contains the comprehensive security and compliance configurations for the LLMOptimizer platform.

## Overview

The security framework implements defense-in-depth principles with multiple layers:

1. **Network Security** - Network policies for micro-segmentation
2. **Pod Security** - Security standards and admission controls
3. **Access Control** - RBAC policies for least privilege
4. **Secrets Management** - Encrypted secrets with rotation
5. **Audit & Compliance** - Comprehensive audit logging
6. **Runtime Security** - Admission webhooks and policy enforcement

## Components

### 1. Network Policies (`network-policies.yaml`)

Implements zero-trust networking with:
- Default deny-all policy
- Explicit allow rules for service communication
- DNS access configuration
- Monitoring endpoint access

### 2. Pod Security Standards (`pod-security-standards.yaml`)

Enforces container security best practices:
- Restricted namespace labels
- Security contexts (non-root, read-only filesystem)
- Resource quotas and limits
- Pod disruption budgets
- Seccomp and AppArmor profiles

### 3. RBAC Policies (`rbac-policies.yaml`)

Implements least-privilege access control:
- Service accounts for each microservice
- Minimal permissions per service
- Developer and admin roles
- Audit role for compliance

### 4. Admission Control (`admission-control.yaml`)

Validates and mutates resources:
- ValidatingWebhooks for security validation
- MutatingWebhooks for security defaults
- Image scanning policies
- OPA (Open Policy Agent) rules
- Falco runtime security rules

### 5. Audit Policy (`audit-policy.yaml`)

Comprehensive audit logging for compliance:
- Detailed logging of sensitive operations
- RBAC change tracking
- Secret access monitoring
- Exec/port-forward tracking
- Alert rules for suspicious activity

### 6. Secrets Management (`secrets-management.yaml`)

Secure secret handling:
- Encryption at rest configuration
- External Secrets Operator integration
- Sealed Secrets for GitOps
- Automatic secret rotation
- Certificate management with cert-manager

## Deployment

### Prerequisites

1. Kubernetes cluster with:
   - RBAC enabled
   - Pod Security Standards support
   - Audit logging enabled
   - cert-manager installed (for TLS)

2. Optional components:
   - External Secrets Operator
   - OPA (Open Policy Agent)
   - Falco for runtime security
   - Vault for secret storage

### Installation Order

```bash
# 1. Create namespace with security labels
kubectl apply -f pod-security-standards.yaml

# 2. Apply RBAC policies
kubectl apply -f rbac-policies.yaml

# 3. Configure network policies
kubectl apply -f network-policies.yaml

# 4. Set up secrets management
kubectl apply -f secrets-management.yaml

# 5. Configure admission control (requires webhook service)
kubectl apply -f admission-control.yaml

# 6. Enable audit logging (requires API server configuration)
# Add audit policy to API server startup parameters
```

## Security Best Practices Implemented

### Container Security
- ✅ Non-root containers
- ✅ Read-only root filesystem
- ✅ No privilege escalation
- ✅ Dropped capabilities
- ✅ Security contexts

### Network Security
- ✅ Network segmentation
- ✅ mTLS via Istio service mesh
- ✅ Ingress/egress controls
- ✅ DNS access restrictions

### Access Control
- ✅ Least privilege RBAC
- ✅ Service accounts per workload
- ✅ No default service account usage
- ✅ Audit logging

### Secret Management
- ✅ Encrypted at rest
- ✅ External secret integration
- ✅ Automatic rotation
- ✅ No hardcoded secrets

### Compliance
- ✅ Comprehensive audit logs
- ✅ Security event alerting
- ✅ Policy enforcement
- ✅ Runtime protection

## Monitoring and Alerting

Security events are monitored through:

1. **Prometheus Alerts** - Real-time security alerts
2. **Audit Log Analysis** - Compliance and forensics
3. **Falco Events** - Runtime anomaly detection
4. **OPA Violations** - Policy violation tracking

## Compliance Frameworks

This security configuration supports:

- **SOC2 Type II** - Security, availability, confidentiality
- **ISO 27001** - Information security management
- **NIST Cybersecurity Framework** - Identify, protect, detect, respond, recover
- **CIS Kubernetes Benchmark** - Security best practices

## Regular Security Tasks

### Daily
- Review security alerts
- Check failed authentication attempts
- Monitor resource usage anomalies

### Weekly
- Review RBAC changes
- Audit secret access logs
- Check compliance reports

### Monthly
- Update security policies
- Review and rotate secrets
- Security training updates

### Quarterly
- Penetration testing
- Security audit
- Policy review and updates

## Troubleshooting

### Common Issues

1. **Pod scheduling failures**
   - Check pod security standards
   - Verify RBAC permissions
   - Review admission webhook logs

2. **Network connectivity issues**
   - Verify network policies
   - Check Istio sidecar injection
   - Review service mesh configuration

3. **Secret access denied**
   - Check RBAC bindings
   - Verify secret exists
   - Review audit logs

## Additional Resources

- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)