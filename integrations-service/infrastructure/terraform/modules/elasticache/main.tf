# ElastiCache Module - Main Configuration

locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = "elasticache"
    }
  )
  
  # Determine if we're creating a cluster mode enabled configuration
  cluster_mode_enabled = var.num_node_groups > 1
}

# Generate random auth token if enabled
resource "random_password" "auth_token" {
  count = var.auth_token_enabled && var.transit_encryption_enabled ? 1 : 0

  length  = 32
  special = true
  
  # ElastiCache AUTH tokens have specific requirements
  override_special = "!&#$^<>-"
}

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.cluster_id}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_id}-subnet-group"
    }
  )
}

# Security Group for ElastiCache
resource "aws_security_group" "elasticache" {
  name        = "${var.cluster_id}-elasticache-sg"
  description = "Security group for ${var.cluster_id} ElastiCache cluster"
  vpc_id      = var.vpc_id

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_id}-elasticache-sg"
    }
  )
}

# Security Group Rules
resource "aws_security_group_rule" "elasticache_ingress_cidr" {
  count = length(var.allowed_cidr_blocks) > 0 ? 1 : 0

  type              = "ingress"
  from_port         = var.port
  to_port           = var.port
  protocol          = "tcp"
  cidr_blocks       = var.allowed_cidr_blocks
  security_group_id = aws_security_group.elasticache.id
}

resource "aws_security_group_rule" "elasticache_ingress_security_groups" {
  count = length(var.security_group_ids)

  type                     = "ingress"
  from_port                = var.port
  to_port                  = var.port
  protocol                 = "tcp"
  source_security_group_id = var.security_group_ids[count.index]
  security_group_id        = aws_security_group.elasticache.id
}

resource "aws_security_group_rule" "elasticache_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.elasticache.id
}

# KMS key for encryption
resource "aws_kms_key" "elasticache" {
  count = var.at_rest_encryption_enabled ? 1 : 0

  description             = "KMS key for ${var.cluster_id} ElastiCache encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_id}-elasticache-key"
    }
  )
}

resource "aws_kms_alias" "elasticache" {
  count = var.at_rest_encryption_enabled ? 1 : 0

  name          = "alias/${var.cluster_id}-elasticache"
  target_key_id = aws_kms_key.elasticache[0].key_id
}

# ElastiCache Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.cluster_id}-params"
  family = var.parameter_group_family

  # Common Redis parameters
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  # Enable Redis keyspace notifications for cache invalidation
  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_id}-params"
    }
  )
}

# ElastiCache Replication Group (for Redis)
resource "aws_elasticache_replication_group" "main" {
  count = var.engine == "redis" ? 1 : 0

  replication_group_id = var.cluster_id
  description          = "${var.cluster_id} Redis replication group"

  engine               = var.engine
  engine_version       = var.engine_version
  node_type            = var.node_type
  port                 = var.port
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.elasticache.id]

  # High Availability settings
  automatic_failover_enabled = var.automatic_failover_enabled
  multi_az_enabled           = var.multi_az_enabled

  # Cluster mode configuration
  num_node_groups         = var.num_node_groups
  replicas_per_node_group = var.replicas_per_node_group

  # Security settings
  at_rest_encryption_enabled = var.at_rest_encryption_enabled
  transit_encryption_enabled = var.transit_encryption_enabled
  auth_token                 = var.auth_token_enabled && var.transit_encryption_enabled ? random_password.auth_token[0].result : null
  kms_key_id                 = var.at_rest_encryption_enabled ? aws_kms_key.elasticache[0].arn : null

  # Backup settings
  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = var.snapshot_window

  # Maintenance settings
  maintenance_window         = var.maintenance_window
  auto_minor_version_upgrade = var.auto_minor_version_upgrade
  apply_immediately          = var.apply_immediately

  # Notification settings
  notification_topic_arn = var.notification_topic_arn

  # Data tiering (for r6gd nodes)
  data_tiering_enabled = var.data_tiering_enabled

  # Log delivery configuration
  dynamic "log_delivery_configuration" {
    for_each = var.log_delivery_configuration
    content {
      destination      = log_delivery_configuration.value.destination
      destination_type = log_delivery_configuration.value.destination_type
      log_format       = log_delivery_configuration.value.log_format
      log_type         = log_delivery_configuration.value.log_type
    }
  }

  lifecycle {
    ignore_changes = [auth_token]
  }

  tags = merge(
    local.common_tags,
    {
      Name = var.cluster_id
    }
  )
}

# ElastiCache Cluster (for Memcached)
resource "aws_elasticache_cluster" "main" {
  count = var.engine == "memcached" ? 1 : 0

  cluster_id           = var.cluster_id
  engine               = var.engine
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_nodes      = var.number_cache_nodes
  port                 = var.port
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.elasticache.id]

  maintenance_window         = var.maintenance_window
  auto_minor_version_upgrade = var.auto_minor_version_upgrade
  apply_immediately          = var.apply_immediately
  notification_topic_arn     = var.notification_topic_arn

  tags = merge(
    local.common_tags,
    {
      Name = var.cluster_id
    }
  )
}

# Store auth token in AWS Secrets Manager
resource "aws_secretsmanager_secret" "elasticache_auth" {
  count = var.auth_token_enabled && var.transit_encryption_enabled && var.engine == "redis" ? 1 : 0

  name                    = "${var.cluster_id}-auth-token"
  description             = "Auth token for ElastiCache cluster ${var.cluster_id}"
  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_id}-auth-token"
    }
  )
}

resource "aws_secretsmanager_secret_version" "elasticache_auth" {
  count = var.auth_token_enabled && var.transit_encryption_enabled && var.engine == "redis" ? 1 : 0

  secret_id = aws_secretsmanager_secret.elasticache_auth[0].id
  secret_string = jsonencode({
    auth_token = random_password.auth_token[0].result
    endpoint   = aws_elasticache_replication_group.main[0].configuration_endpoint_address
    port       = var.port
    engine     = var.engine
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  count = var.engine == "redis" ? 1 : 0

  alarm_name          = "${var.cluster_id}-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "This metric monitors ElastiCache CPU utilization"

  dimensions = {
    CacheClusterId = var.cluster_id
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "memory_utilization" {
  count = var.engine == "redis" ? 1 : 0

  alarm_name          = "${var.cluster_id}-memory-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "90"
  alarm_description   = "This metric monitors ElastiCache memory utilization"

  dimensions = {
    CacheClusterId = var.cluster_id
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "evictions" {
  count = var.engine == "redis" ? 1 : 0

  alarm_name          = "${var.cluster_id}-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "This metric monitors ElastiCache evictions"

  dimensions = {
    CacheClusterId = var.cluster_id
  }

  tags = local.common_tags
}