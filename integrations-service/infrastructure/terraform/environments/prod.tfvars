# Production Environment Configuration

# General Settings
environment = "prod"
region      = "us-east-1"
project     = "llmoptimizer"

# VPC Configuration
vpc_cidr = "10.2.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
public_subnet_cidrs = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
private_subnet_cidrs = ["10.2.11.0/24", "10.2.12.0/24", "10.2.13.0/24"]
database_subnet_cidrs = ["10.2.21.0/24", "10.2.22.0/24", "10.2.23.0/24"]

# Full resilience and monitoring
single_nat_gateway = false
enable_flow_logs = true
flow_logs_retention_days = 30

# EKS Configuration
eks_cluster_version = "1.28"
eks_node_groups = {
  system = {
    desired_size   = 3
    min_size       = 3
    max_size       = 5
    instance_types = ["m5.large"]
    capacity_type  = "ON_DEMAND"
    disk_size      = 100
    labels = {
      role = "system"
    }
    taints = [{
      key    = "CriticalAddonsOnly"
      value  = "true"
      effect = "NoSchedule"
    }]
  }
  general = {
    desired_size   = 6
    min_size       = 3
    max_size       = 12
    instance_types = ["m5.xlarge"]
    capacity_type  = "ON_DEMAND"
    disk_size      = 200
    labels = {
      role = "general"
    }
    taints = []
  }
  spot = {
    desired_size   = 4
    min_size       = 2
    max_size       = 8
    instance_types = ["m5.xlarge", "m5a.xlarge", "m5n.xlarge"]
    capacity_type  = "SPOT"
    disk_size      = 200
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
rds_instance_class = "db.r6g.xlarge"
rds_allocated_storage = 500
rds_storage_type = "gp3"
rds_iops = 3000
rds_multi_az = true
rds_backup_retention_period = 30
rds_deletion_protection = true
rds_skip_final_snapshot = false
rds_performance_insights_enabled = true
rds_performance_insights_retention_period = 7
rds_monitoring_interval = 60

# ElastiCache Configuration
elasticache_node_type = "cache.r6g.large"
elasticache_num_node_groups = 3
elasticache_replicas_per_node_group = 2
elasticache_automatic_failover = true
elasticache_multi_az = true
elasticache_snapshot_retention_limit = 14
elasticache_data_tiering_enabled = false

# S3 Configuration
s3_force_destroy = false
s3_versioning_enabled = true
s3_enable_intelligent_tiering = true
s3_lifecycle_rules = [
  {
    id      = "transition-old-versions"
    enabled = true
    prefix  = ""
    
    noncurrent_version_transition = [
      {
        days          = 30
        storage_class = "STANDARD_IA"
      },
      {
        days          = 60
        storage_class = "GLACIER"
      }
    ]
    
    noncurrent_version_expiration = {
      days = 365
    }
  },
  {
    id      = "archive-logs"
    enabled = true
    prefix  = "logs/"
    
    transition = [
      {
        days          = 7
        storage_class = "STANDARD_IA"
      },
      {
        days          = 30
        storage_class = "GLACIER"
      }
    ]
    
    expiration = {
      days = 365
    }
  }
]

# ALB Configuration
alb_deletion_protection = true
alb_idle_timeout = 300
alb_access_logs_enabled = true
alb_access_logs_bucket = "llmoptimizer-prod-alb-logs"
alb_enable_waf = true
alb_enable_shield_advanced = true

# Disaster Recovery - Secondary Region
dr_region = "us-west-2"
dr_vpc_cidr = "10.3.0.0/16"
enable_cross_region_replication = true

# Cost Estimation: ~$2,500-3,500/month
# - EKS: ~$73/month (cluster) + ~$1,200/month (nodes)
# - RDS: ~$400/month (r6g.xlarge Multi-AZ)
# - ElastiCache: ~$600/month (3x r6g.large with replicas)
# - ALB: ~$50/month
# - NAT Gateways: ~$135/month (3x)
# - S3/Data Transfer: ~$200-500/month
# - CloudWatch/Monitoring: ~$100-200/month
# - Shield Advanced: ~$3,000/month (if enabled)

# Tags
tags = {
  Environment     = "prod"
  Project         = "llmoptimizer"
  ManagedBy       = "terraform"
  CostCenter      = "production"
  DataClass       = "confidential"
  Compliance      = "soc2"
  BackupSchedule  = "daily"
  MonitoringLevel = "enhanced"
}