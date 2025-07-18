# Main Outputs

# VPC Outputs
output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "database_subnet_ids" {
  description = "List of database subnet IDs"
  value       = module.vpc.database_subnet_ids
}

output "nat_gateway_ips" {
  description = "List of NAT Gateway public IPs"
  value       = module.vpc.nat_gateway_public_ips
}

# EKS Outputs
output "eks_cluster_id" {
  description = "The name/id of the EKS cluster"
  value       = module.eks.cluster_id
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "eks_node_group_security_group_id" {
  description = "Security group ID attached to the EKS nodes"
  value       = module.eks.node_group_security_group_id
}

output "eks_oidc_provider_arn" {
  description = "ARN of the OIDC Provider for IRSA"
  value       = module.eks.oidc_provider_arn
}

output "eks_kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = module.eks.kubeconfig_command
}

# RDS Outputs
output "rds_endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = module.rds_postgresql.db_instance_endpoint
  sensitive   = true
}

output "rds_database_name" {
  description = "The database name"
  value       = module.rds_postgresql.db_instance_database_name
}

output "rds_username" {
  description = "The master username for the database"
  value       = module.rds_postgresql.db_instance_username
  sensitive   = true
}

output "rds_secret_arn" {
  description = "The ARN of the secret containing the database credentials"
  value       = module.rds_postgresql.secret_arn
}

output "rds_security_group_id" {
  description = "The security group ID of the RDS instance"
  value       = module.rds_postgresql.db_instance_security_group_id
}

# ElastiCache Outputs
output "redis_endpoint" {
  description = "The Redis primary endpoint address"
  value       = module.elasticache_redis.primary_endpoint_address
}

output "redis_configuration_endpoint" {
  description = "The Redis configuration endpoint (cluster mode)"
  value       = module.elasticache_redis.configuration_endpoint_address
}

output "redis_port" {
  description = "The Redis port"
  value       = module.elasticache_redis.port
}

output "redis_secret_arn" {
  description = "The ARN of the secret containing the Redis auth token"
  value       = module.elasticache_redis.secret_arn
}

output "redis_security_group_id" {
  description = "The security group ID of the Redis cluster"
  value       = module.elasticache_redis.security_group_id
}

# S3 Outputs
output "s3_storage_bucket" {
  description = "The name of the storage S3 bucket"
  value       = module.s3_storage.bucket_id
}

output "s3_storage_bucket_arn" {
  description = "The ARN of the storage S3 bucket"
  value       = module.s3_storage.bucket_arn
}

output "s3_alb_logs_bucket" {
  description = "The name of the ALB logs S3 bucket"
  value       = var.alb_access_logs_enabled ? module.s3_alb_logs[0].bucket_id : null
}

# ALB Outputs
output "alb_dns_name" {
  description = "The DNS name of the load balancer"
  value       = module.alb.lb_dns_name
}

output "alb_zone_id" {
  description = "The zone ID of the load balancer"
  value       = module.alb.lb_zone_id
}

output "alb_arn" {
  description = "The ARN of the load balancer"
  value       = module.alb.lb_arn
}

output "alb_target_group_arns" {
  description = "Map of target group ARNs"
  value       = module.alb.target_group_arns
}

output "alb_security_group_id" {
  description = "The security group ID of the load balancer"
  value       = module.alb.security_group_id
}

# Environment Information
output "environment" {
  description = "The environment name"
  value       = var.environment
}

output "region" {
  description = "The AWS region"
  value       = var.region
}

output "project" {
  description = "The project name"
  value       = var.project
}

# Connection Strings (for application configuration)
output "database_connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = module.rds_postgresql.connection_string
  sensitive   = true
}

output "redis_connection_string" {
  description = "Redis connection string (without auth token)"
  value       = module.elasticache_redis.redis_connection_string
  sensitive   = true
}

output "redis_connection_string_tls" {
  description = "Redis TLS connection string (without auth token)"
  value       = module.elasticache_redis.redis_connection_string_tls
  sensitive   = true
}

# Cost Tracking
output "estimated_monthly_cost" {
  description = "Estimated monthly cost based on environment"
  value = {
    dev     = "$250-350"
    staging = "$600-800"
    prod    = "$2,500-3,500 (without Shield Advanced)"
  }[var.environment]
}