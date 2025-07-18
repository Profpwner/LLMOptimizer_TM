# Staging Environment Configuration

# General Settings
environment = "staging"
region      = "us-east-1"
project     = "llmoptimizer"

# VPC Configuration
vpc_cidr = "10.1.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
public_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
private_subnet_cidrs = ["10.1.11.0/24", "10.1.12.0/24", "10.1.13.0/24"]
database_subnet_cidrs = ["10.1.21.0/24", "10.1.22.0/24", "10.1.23.0/24"]

# More resilient than dev, but still cost-conscious
single_nat_gateway = false  # NAT gateway per AZ
enable_flow_logs = true
flow_logs_retention_days = 7

# EKS Configuration
eks_cluster_version = "1.28"
eks_node_groups = {
  general = {
    desired_size   = 3
    min_size       = 2
    max_size       = 6
    instance_types = ["t3.large"]
    capacity_type  = "ON_DEMAND"
    disk_size      = 100
    labels = {
      role = "general"
    }
    taints = []
  }
  spot = {
    desired_size   = 2
    min_size       = 1
    max_size       = 4
    instance_types = ["t3.large", "t3a.large"]
    capacity_type  = "SPOT"
    disk_size      = 100
    labels = {
      role = "spot"
    }
    taints = [{
      key    = "spot"
      value  = "true"
      effect = "NoSchedule"
    }]
  }
}

# RDS Configuration
rds_instance_class = "db.t3.medium"
rds_allocated_storage = 100
rds_multi_az = true
rds_backup_retention_period = 14
rds_deletion_protection = true
rds_skip_final_snapshot = false
rds_performance_insights_enabled = true

# ElastiCache Configuration
elasticache_node_type = "cache.t3.small"
elasticache_num_cache_nodes = 2
elasticache_automatic_failover = true
elasticache_multi_az = true
elasticache_snapshot_retention_limit = 7

# S3 Configuration
s3_force_destroy = false
s3_versioning_enabled = true
s3_lifecycle_rules = [
  {
    id      = "transition-old-versions"
    enabled = true
    prefix  = ""
    
    noncurrent_version_transition = [{
      days          = 30
      storage_class = "STANDARD_IA"
    }]
    
    noncurrent_version_expiration = {
      days = 90
    }
  }
]

# ALB Configuration
alb_deletion_protection = true
alb_idle_timeout = 120
alb_access_logs_enabled = true
alb_access_logs_bucket = "llmoptimizer-staging-alb-logs"

# Cost Estimation: ~$600-800/month
# - EKS: ~$73/month (cluster) + ~$200/month (nodes)
# - RDS: ~$100/month (t3.medium Multi-AZ)
# - ElastiCache: ~$50/month (2x t3.small)
# - ALB: ~$25/month
# - NAT Gateways: ~$135/month (3x)
# - S3/Data Transfer: ~$50-100/month

# Tags
tags = {
  Environment = "staging"
  Project     = "llmoptimizer"
  ManagedBy   = "terraform"
  CostCenter  = "engineering"
}