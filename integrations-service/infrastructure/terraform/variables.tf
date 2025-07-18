# Main Variables Configuration

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "project" {
  description = "Project name"
  type        = string
}

# VPC Variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use a single NAT Gateway for all private subnets"
  type        = bool
  default     = false
}

variable "enable_flow_logs" {
  description = "Enable VPC flow logs"
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "VPC flow logs retention in days"
  type        = number
  default     = 30
}

# EKS Variables
variable "eks_cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
}

variable "eks_node_groups" {
  description = "Map of EKS node group configurations"
  type = map(object({
    desired_size   = number
    min_size       = number
    max_size       = number
    instance_types = list(string)
    capacity_type  = string
    disk_size      = number
    labels         = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
}

# RDS Variables
variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
}

variable "rds_storage_type" {
  description = "RDS storage type"
  type        = string
  default     = "gp3"
}

variable "rds_iops" {
  description = "RDS provisioned IOPS"
  type        = number
  default     = null
}

variable "rds_multi_az" {
  description = "Enable RDS Multi-AZ"
  type        = bool
}

variable "rds_backup_retention_period" {
  description = "RDS backup retention period in days"
  type        = number
}

variable "rds_deletion_protection" {
  description = "Enable RDS deletion protection"
  type        = bool
}

variable "rds_skip_final_snapshot" {
  description = "Skip final snapshot on RDS deletion"
  type        = bool
}

variable "rds_performance_insights_enabled" {
  description = "Enable RDS Performance Insights"
  type        = bool
  default     = false
}

variable "rds_performance_insights_retention_period" {
  description = "Performance Insights retention period in days"
  type        = number
  default     = 7
}

variable "rds_monitoring_interval" {
  description = "RDS enhanced monitoring interval"
  type        = number
  default     = 0
}

# ElastiCache Variables
variable "elasticache_node_type" {
  description = "ElastiCache node type"
  type        = string
}

variable "elasticache_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

variable "elasticache_num_node_groups" {
  description = "Number of node groups (shards)"
  type        = number
  default     = 1
}

variable "elasticache_replicas_per_node_group" {
  description = "Number of replicas per node group"
  type        = number
  default     = 0
}

variable "elasticache_automatic_failover" {
  description = "Enable automatic failover"
  type        = bool
}

variable "elasticache_multi_az" {
  description = "Enable Multi-AZ"
  type        = bool
}

variable "elasticache_snapshot_retention_limit" {
  description = "Snapshot retention limit in days"
  type        = number
}

variable "elasticache_data_tiering_enabled" {
  description = "Enable data tiering for r6gd nodes"
  type        = bool
  default     = false
}

# S3 Variables
variable "s3_force_destroy" {
  description = "Allow S3 bucket destruction with objects"
  type        = bool
}

variable "s3_versioning_enabled" {
  description = "Enable S3 versioning"
  type        = bool
}

variable "s3_enable_intelligent_tiering" {
  description = "Enable S3 Intelligent-Tiering"
  type        = bool
  default     = false
}

variable "s3_lifecycle_rules" {
  description = "S3 lifecycle rules"
  type        = list(any)
  default     = []
}

# ALB Variables
variable "alb_deletion_protection" {
  description = "Enable ALB deletion protection"
  type        = bool
}

variable "alb_idle_timeout" {
  description = "ALB idle timeout in seconds"
  type        = number
}

variable "alb_access_logs_enabled" {
  description = "Enable ALB access logs"
  type        = bool
}

variable "alb_access_logs_bucket" {
  description = "S3 bucket for ALB access logs"
  type        = string
  default     = null
}

variable "alb_enable_waf" {
  description = "Enable WAF for ALB"
  type        = bool
  default     = false
}

variable "alb_enable_shield_advanced" {
  description = "Enable Shield Advanced for ALB"
  type        = bool
  default     = false
}

# Disaster Recovery Variables
variable "dr_region" {
  description = "Disaster recovery region"
  type        = string
  default     = null
}

variable "dr_vpc_cidr" {
  description = "CIDR block for DR VPC"
  type        = string
  default     = null
}

variable "enable_cross_region_replication" {
  description = "Enable cross-region replication"
  type        = bool
  default     = false
}

# Tags
variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}