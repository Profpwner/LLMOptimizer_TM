# Main Terraform Configuration

locals {
  name_prefix = "${var.project}-${var.environment}"
  
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      Project     = var.project
      ManagedBy   = "terraform"
      Region      = var.region
    }
  )
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  name                     = local.name_prefix
  environment              = var.environment
  region                   = var.region
  cidr_block               = var.vpc_cidr
  availability_zones       = var.availability_zones
  public_subnet_cidrs      = var.public_subnet_cidrs
  private_subnet_cidrs     = var.private_subnet_cidrs
  database_subnet_cidrs    = var.database_subnet_cidrs
  single_nat_gateway       = var.single_nat_gateway
  enable_nat_gateway       = true
  enable_dns_hostnames     = true
  enable_dns_support       = true
  enable_flow_logs         = var.enable_flow_logs
  flow_logs_retention_days = var.flow_logs_retention_days
  tags                     = local.common_tags
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  cluster_name                 = "${local.name_prefix}-eks"
  cluster_version              = var.eks_cluster_version
  environment                  = var.environment
  vpc_id                       = module.vpc.vpc_id
  subnet_ids                   = module.vpc.private_subnet_ids
  enable_irsa                  = true
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true
  cluster_endpoint_public_access_cidrs = ["0.0.0.0/0"]  # Restrict in production
  
  node_groups = var.eks_node_groups
  
  enable_cluster_autoscaler           = true
  enable_metrics_server               = true
  enable_aws_load_balancer_controller = true
  enable_external_dns                 = false
  enable_cert_manager                 = false
  
  cluster_log_types           = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cluster_log_retention_days  = var.flow_logs_retention_days
  
  tags = local.common_tags
}

# RDS Module - PostgreSQL
module "rds_postgresql" {
  source = "./modules/rds"

  identifier                   = "${local.name_prefix}-postgres"
  environment                  = var.environment
  engine                       = "postgres"
  engine_version               = "15.4"
  instance_class               = var.rds_instance_class
  allocated_storage            = var.rds_allocated_storage
  storage_type                 = var.rds_storage_type
  storage_encrypted            = true
  iops                         = var.rds_iops
  database_name                = "llmoptimizer"
  username                     = "dbadmin"
  create_random_password       = true
  port                         = 5432
  vpc_id                       = module.vpc.vpc_id
  subnet_ids                   = module.vpc.database_subnet_ids
  multi_az                     = var.rds_multi_az
  publicly_accessible          = false
  vpc_security_group_ids       = [module.eks.node_group_security_group_id]
  
  backup_retention_period                = var.rds_backup_retention_period
  backup_window                          = "03:00-04:00"
  maintenance_window                     = "sun:04:00-sun:05:00"
  deletion_protection                    = var.rds_deletion_protection
  skip_final_snapshot                    = var.rds_skip_final_snapshot
  
  performance_insights_enabled           = var.rds_performance_insights_enabled
  performance_insights_retention_period  = var.rds_performance_insights_retention_period
  monitoring_interval                    = var.rds_monitoring_interval
  enabled_cloudwatch_logs_exports        = ["postgresql"]
  
  tags = local.common_tags
}

# ElastiCache Module - Redis
module "elasticache_redis" {
  source = "./modules/elasticache"

  cluster_id                  = "${local.name_prefix}-redis"
  environment                 = var.environment
  engine                      = "redis"
  engine_version              = "7.0"
  node_type                   = var.elasticache_node_type
  parameter_group_family      = "redis7"
  port                        = 6379
  vpc_id                      = module.vpc.vpc_id
  subnet_ids                  = module.vpc.private_subnet_ids
  security_group_ids          = [module.eks.node_group_security_group_id]
  
  num_node_groups             = var.elasticache_num_node_groups
  replicas_per_node_group     = var.elasticache_replicas_per_node_group
  automatic_failover_enabled  = var.elasticache_automatic_failover
  multi_az_enabled            = var.elasticache_multi_az
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  auth_token_enabled          = true
  data_tiering_enabled        = var.elasticache_data_tiering_enabled
  
  snapshot_retention_limit    = var.elasticache_snapshot_retention_limit
  snapshot_window             = "03:00-05:00"
  maintenance_window          = "sun:05:00-sun:06:00"
  
  tags = local.common_tags
}

# S3 Buckets
module "s3_storage" {
  source = "./modules/s3"

  bucket_name                = "${local.name_prefix}-storage"
  environment                = var.environment
  force_destroy              = var.s3_force_destroy
  versioning_enabled         = var.s3_versioning_enabled
  enable_encryption          = true
  block_public_acls          = true
  block_public_policy        = true
  ignore_public_acls         = true
  restrict_public_buckets    = true
  enable_intelligent_tiering = var.s3_enable_intelligent_tiering
  lifecycle_rules            = var.s3_lifecycle_rules
  
  cors_rules = [{
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["*"]  # Restrict in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }]
  
  tags = local.common_tags
}

# S3 Bucket for ALB Logs
module "s3_alb_logs" {
  source = "./modules/s3"
  count  = var.alb_access_logs_enabled ? 1 : 0

  bucket_name             = var.alb_access_logs_bucket != null ? var.alb_access_logs_bucket : "${local.name_prefix}-alb-logs"
  environment             = var.environment
  force_destroy           = var.s3_force_destroy
  versioning_enabled      = false
  enable_encryption       = true
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  
  lifecycle_rules = [{
    id      = "cleanup-old-logs"
    enabled = true
    prefix  = ""
    
    transition = [{
      days          = 30
      storage_class = "STANDARD_IA"
    }]
    
    expiration = {
      days = 90
    }
  }]
  
  # Bucket policy to allow ALB to write logs
  bucket_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::127311923021:root"  # US East 1 ELB service account
        }
        Action   = "s3:PutObject"
        Resource = "arn:aws:s3:::${var.alb_access_logs_bucket != null ? var.alb_access_logs_bucket : "${local.name_prefix}-alb-logs"}/*"
      }
    ]
  })
  
  tags = local.common_tags
}

# Application Load Balancer
module "alb" {
  source = "./modules/alb"

  name                       = "${local.name_prefix}-alb"
  environment                = var.environment
  internal                   = false
  vpc_id                     = module.vpc.vpc_id
  subnets                    = module.vpc.public_subnet_ids
  enable_deletion_protection = var.alb_deletion_protection
  enable_http2               = true
  idle_timeout               = var.alb_idle_timeout
  
  access_logs = {
    enabled = var.alb_access_logs_enabled
    bucket  = var.alb_access_logs_enabled ? module.s3_alb_logs[0].bucket_id : null
    prefix  = "alb-logs"
  }
  
  ingress_rules = [
    {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "HTTP from Internet"
    },
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "HTTPS from Internet"
    }
  ]
  
  target_groups = [
    {
      name                 = "${local.name_prefix}-api"
      port                 = 8080
      protocol             = "HTTP"
      target_type          = "ip"
      deregistration_delay = 30
      
      health_check = {
        enabled             = true
        healthy_threshold   = 2
        unhealthy_threshold = 2
        timeout             = 5
        interval            = 30
        matcher             = "200-299"
        path                = "/health"
        port                = "traffic-port"
      }
      
      stickiness = {
        enabled         = true
        type            = "lb_cookie"
        cookie_duration = 86400
      }
    },
    {
      name                 = "${local.name_prefix}-websocket"
      port                 = 8081
      protocol             = "HTTP"
      target_type          = "ip"
      deregistration_delay = 30
      
      health_check = {
        enabled             = true
        healthy_threshold   = 2
        unhealthy_threshold = 2
        timeout             = 5
        interval            = 30
        matcher             = "200-299"
        path                = "/ws/health"
        port                = "traffic-port"
      }
      
      stickiness = {
        enabled         = true
        type            = "lb_cookie"
        cookie_duration = 86400
      }
    }
  ]
  
  listeners = [
    {
      port     = 80
      protocol = "HTTP"
      
      default_action = {
        type = "redirect"
        redirect = {
          port        = "443"
          protocol    = "HTTPS"
          status_code = "HTTP_301"
        }
      }
    }
  ]
  
  enable_waf             = var.alb_enable_waf
  enable_shield_advanced = var.alb_enable_shield_advanced
  
  tags = local.common_tags
}