# LLMOptimizer Infrastructure as Code

This directory contains Terraform configurations for provisioning the LLMOptimizer infrastructure on AWS.

## Architecture Overview

The infrastructure includes:
- **VPC** with public, private, and database subnets across multiple AZs
- **EKS Cluster** with managed node groups (on-demand and spot instances)
- **RDS PostgreSQL** for primary database (Multi-AZ in production)
- **ElastiCache Redis** for caching and session management
- **S3 Buckets** for object storage and logs
- **Application Load Balancer** for ingress traffic
- **Security Groups** and **IAM Roles** for secure access control

## Directory Structure

```
terraform/
├── modules/              # Reusable Terraform modules
│   ├── vpc/             # VPC with subnets, NAT gateways
│   ├── eks/             # EKS cluster and node groups
│   ├── rds/             # RDS PostgreSQL instances
│   ├── elasticache/     # ElastiCache Redis clusters
│   ├── s3/              # S3 buckets with lifecycle policies
│   └── alb/             # Application Load Balancer
├── environments/         # Environment-specific configurations
│   ├── dev.tfvars       # Development environment
│   ├── staging.tfvars   # Staging environment
│   └── prod.tfvars      # Production environment
├── main.tf              # Main Terraform configuration
├── variables.tf         # Variable definitions
├── outputs.tf           # Output definitions
├── providers.tf         # Provider configurations
├── versions.tf          # Version constraints
└── backend.tf           # Remote state configuration
```

## Prerequisites

1. **Terraform**: Version 1.5.0 or higher
2. **AWS CLI**: Configured with appropriate credentials
3. **kubectl**: For interacting with EKS cluster
4. **helm**: For deploying applications to Kubernetes

## Quick Start

### 1. Initialize Terraform

```bash
terraform init
```

### 2. Configure Backend (Optional but Recommended)

Edit `backend.tf` to configure S3 backend for remote state:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "llmoptimizer/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

### 3. Deploy Infrastructure

#### Development Environment
```bash
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

#### Staging Environment
```bash
terraform plan -var-file=environments/staging.tfvars
terraform apply -var-file=environments/staging.tfvars
```

#### Production Environment
```bash
terraform plan -var-file=environments/prod.tfvars
terraform apply -var-file=environments/prod.tfvars
```

### 4. Configure kubectl

After the EKS cluster is created:

```bash
aws eks update-kubeconfig --region $(terraform output -raw region) --name $(terraform output -raw eks_cluster_id)
```

## Cost Estimates

### Development Environment (~$250-350/month)
- EKS: ~$73/month (cluster) + ~$30-50/month (2x t3.medium SPOT)
- RDS: ~$25/month (t3.small)
- ElastiCache: ~$13/month (t3.micro)
- ALB: ~$20/month
- NAT Gateway: ~$45/month (single NAT)
- S3/Data Transfer: ~$20-50/month

### Staging Environment (~$600-800/month)
- EKS: ~$73/month (cluster) + ~$200/month (mixed on-demand/spot)
- RDS: ~$100/month (t3.medium Multi-AZ)
- ElastiCache: ~$50/month (2x t3.small)
- ALB: ~$25/month
- NAT Gateways: ~$135/month (3x NAT)
- S3/Data Transfer: ~$50-100/month

### Production Environment (~$2,500-3,500/month)
- EKS: ~$73/month (cluster) + ~$1,200/month (multiple node groups)
- RDS: ~$400/month (r6g.xlarge Multi-AZ)
- ElastiCache: ~$600/month (3x r6g.large with replicas)
- ALB: ~$50/month
- NAT Gateways: ~$135/month (3x NAT)
- S3/Data Transfer: ~$200-500/month
- CloudWatch/Monitoring: ~$100-200/month

**Note**: Shield Advanced adds ~$3,000/month if enabled in production.

## Key Features by Environment

### Development
- Single NAT gateway (cost optimization)
- SPOT instances for worker nodes
- Minimal redundancy
- Reduced backup retention
- No deletion protection

### Staging
- Multi-AZ deployment
- Mix of on-demand and SPOT instances
- Flow logs enabled
- Performance insights enabled
- Deletion protection on critical resources

### Production
- Full Multi-AZ redundancy
- Multiple node groups with taints/tolerations
- Enhanced monitoring and logging
- Extended backup retention (30 days)
- Intelligent tiering for S3
- Optional WAF and Shield Advanced
- Disaster recovery readiness

## Module Details

### VPC Module
- Creates VPC with configurable CIDR blocks
- Public, private, and database subnets
- NAT gateways for private subnet internet access
- VPC flow logs (optional)
- S3 VPC endpoint for cost optimization

### EKS Module
- Managed EKS cluster with OIDC provider
- Multiple node groups with auto-scaling
- IRSA (IAM Roles for Service Accounts)
- Pre-configured IAM policies for common controllers
- Cluster autoscaler support
- CloudWatch logs for audit trails

### RDS Module
- PostgreSQL 15.4 by default
- Automated backups with point-in-time recovery
- Performance Insights (staging/prod)
- Enhanced monitoring
- Encryption at rest with KMS
- Secrets Manager integration

### ElastiCache Module
- Redis 7.0 cluster
- Cluster mode support for sharding
- Automatic failover
- Encryption in transit and at rest
- AUTH token stored in Secrets Manager

### S3 Module
- Server-side encryption with KMS
- Versioning and lifecycle policies
- CORS configuration
- Intelligent tiering support
- Public access blocked by default

### ALB Module
- Layer 7 load balancing
- Target group health checks
- SSL/TLS termination
- Access logs to S3
- CloudWatch metrics and alarms

## Security Best Practices

1. **Network Isolation**: Private subnets for compute, separate database subnets
2. **Encryption**: All data encrypted at rest and in transit
3. **IAM**: Least privilege access with IRSA for pods
4. **Secrets**: Database passwords and tokens in AWS Secrets Manager
5. **Security Groups**: Restrictive ingress rules, full egress
6. **KMS**: Customer-managed keys for encryption
7. **VPC Flow Logs**: Network traffic monitoring
8. **Public Access**: Blocked on S3 buckets, databases in private subnets

## Disaster Recovery

### Multi-Region Setup (Production)
- Set `enable_cross_region_replication = true`
- Configure `dr_region` and `dr_vpc_cidr`
- Enables S3 cross-region replication
- Supports RDS read replicas in DR region
- Prepared for quick failover

### Backup Strategy
- **RDS**: Automated daily backups with 30-day retention (prod)
- **ElastiCache**: Daily snapshots with 14-day retention (prod)
- **S3**: Versioning enabled with lifecycle policies
- **EKS**: Cluster configuration in code, stateless design

## Monitoring and Alerts

CloudWatch alarms are created for:
- EKS node CPU/memory utilization
- RDS CPU, connections, and storage
- ElastiCache CPU, memory, and evictions
- ALB target health and response times
- 4xx/5xx error rates

## Maintenance

### Updating Infrastructure
1. Always run `terraform plan` before `apply`
2. Review changes carefully, especially in production
3. Consider using `-target` for specific resource updates
4. Use workspace or branch strategy for testing

### Destroying Resources
```bash
# Remove deletion protection first (if enabled)
terraform apply -var-file=environments/dev.tfvars -var="rds_deletion_protection=false"

# Then destroy
terraform destroy -var-file=environments/dev.tfvars
```

## Troubleshooting

### Common Issues

1. **EKS Node Registration**: Ensure node security groups allow communication
2. **RDS Connection**: Check security group rules and subnet routing
3. **S3 Access**: Verify IAM policies and VPC endpoints
4. **ALB Target Health**: Check application health endpoints

### Useful Commands

```bash
# Check EKS cluster status
aws eks describe-cluster --name $(terraform output -raw eks_cluster_id)

# List node groups
aws eks list-nodegroups --cluster-name $(terraform output -raw eks_cluster_id)

# Get RDS endpoint
terraform output rds_endpoint

# Get ALB DNS name
terraform output alb_dns_name
```

## Next Steps

After infrastructure is provisioned:

1. Deploy Kubernetes manifests or Helm charts
2. Configure DNS records pointing to ALB
3. Set up CI/CD pipelines
4. Configure application secrets in Kubernetes
5. Set up monitoring and logging aggregation
6. Perform security audit and penetration testing

## Support

For issues or questions:
1. Check AWS service limits
2. Review CloudWatch logs
3. Verify IAM permissions
4. Check network connectivity