# Development Environment Configuration

# General Settings
environment = "dev"
region      = "us-east-1"
project     = "llmoptimizer"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]
public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]
database_subnet_cidrs = ["10.0.21.0/24", "10.0.22.0/24"]

# Cost optimization for dev
single_nat_gateway = true
enable_flow_logs = false

# EKS Configuration
eks_cluster_version = "1.28"
eks_node_groups = {
  general = {
    desired_size   = 2
    min_size       = 1
    max_size       = 4
    instance_types = ["t3.medium"]
    capacity_type  = "SPOT"  # Use SPOT instances for cost savings in dev
    disk_size      = 50
    labels = {
      role = "general"
    }
    taints = []
  }
}

# RDS Configuration
rds_instance_class = "db.t3.small"
rds_allocated_storage = 20
rds_multi_az = false  # Single AZ for dev
rds_backup_retention_period = 7
rds_deletion_protection = false
rds_skip_final_snapshot = true

# ElastiCache Configuration
elasticache_node_type = "cache.t3.micro"
elasticache_num_cache_nodes = 1
elasticache_automatic_failover = false
elasticache_multi_az = false
elasticache_snapshot_retention_limit = 3

# S3 Configuration
s3_force_destroy = true  # Allow bucket deletion in dev
s3_versioning_enabled = false
s3_lifecycle_rules = []

# ALB Configuration
alb_deletion_protection = false
alb_idle_timeout = 60
alb_access_logs_enabled = false

# Cost Estimation: ~$250-350/month
# - EKS: ~$73/month (cluster) + ~$30-50/month (2x t3.medium SPOT)
# - RDS: ~$25/month (t3.small)
# - ElastiCache: ~$13/month (t3.micro)
# - ALB: ~$20/month
# - NAT Gateway: ~$45/month
# - S3/Data Transfer: ~$20-50/month

# Tags
tags = {
  Environment = "dev"
  Project     = "llmoptimizer"
  ManagedBy   = "terraform"
  CostCenter  = "development"
}