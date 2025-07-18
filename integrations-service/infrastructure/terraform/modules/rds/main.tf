# RDS Module - Main Configuration

locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = "rds"
    }
  )
  
  create_monitoring_role = var.create_monitoring_role && var.monitoring_interval > 0
}

# Generate random password if requested
resource "random_password" "master" {
  count = var.create_random_password && var.password == null ? 1 : 0

  length  = 32
  special = true
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  count = var.create_db_subnet_group ? 1 : 0

  name       = var.db_subnet_group_name != null ? var.db_subnet_group_name : "${var.identifier}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    local.common_tags,
    {
      Name = "${var.identifier}-subnet-group"
    }
  )
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name        = "${var.identifier}-rds-sg"
  description = "Security group for ${var.identifier} RDS instance"
  vpc_id      = var.vpc_id

  tags = merge(
    local.common_tags,
    {
      Name = "${var.identifier}-rds-sg"
    }
  )
}

# Security Group Rules
resource "aws_security_group_rule" "rds_ingress_cidr" {
  count = length(var.allowed_cidr_blocks) > 0 ? 1 : 0

  type              = "ingress"
  from_port         = var.port
  to_port           = var.port
  protocol          = "tcp"
  cidr_blocks       = var.allowed_cidr_blocks
  security_group_id = aws_security_group.rds.id
}

resource "aws_security_group_rule" "rds_ingress_security_groups" {
  count = length(var.vpc_security_group_ids)

  type                     = "ingress"
  from_port                = var.port
  to_port                  = var.port
  protocol                 = "tcp"
  source_security_group_id = var.vpc_security_group_ids[count.index]
  security_group_id        = aws_security_group.rds.id
}

resource "aws_security_group_rule" "rds_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.rds.id
}

# KMS key for encryption
resource "aws_kms_key" "rds" {
  count = var.storage_encrypted ? 1 : 0

  description             = "KMS key for ${var.identifier} RDS encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${var.identifier}-rds-key"
    }
  )
}

resource "aws_kms_alias" "rds" {
  count = var.storage_encrypted ? 1 : 0

  name          = "alias/${var.identifier}-rds"
  target_key_id = aws_kms_key.rds[0].key_id
}

# IAM role for enhanced monitoring
resource "aws_iam_role" "enhanced_monitoring" {
  count = local.create_monitoring_role ? 1 : 0

  name = "${var.identifier}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "enhanced_monitoring" {
  count = local.create_monitoring_role ? 1 : 0

  role       = aws_iam_role.enhanced_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# DB Parameter Group
resource "aws_db_parameter_group" "main" {
  name   = "${var.identifier}-params"
  family = var.parameter_group_family

  dynamic "parameter" {
    for_each = var.parameters
    content {
      name  = parameter.value.name
      value = parameter.value.value
    }
  }

  # Default parameters for PostgreSQL
  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # Log queries taking more than 1 second
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.identifier}-params"
    }
  )
}

# DB Option Group (for specific engines)
resource "aws_db_option_group" "main" {
  count = length(var.options) > 0 ? 1 : 0

  name                     = "${var.identifier}-options"
  option_group_description = "Option group for ${var.identifier}"
  engine_name              = var.engine
  major_engine_version     = split(".", var.engine_version)[0]

  dynamic "option" {
    for_each = var.options
    content {
      option_name = option.value.option_name

      dynamic "option_settings" {
        for_each = lookup(option.value, "option_settings", [])
        content {
          name  = option_settings.value.name
          value = option_settings.value.value
        }
      }
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.identifier}-options"
    }
  )
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = var.identifier

  # Engine options
  engine                    = var.engine
  engine_version            = var.engine_version
  allow_major_version_upgrade = var.allow_major_version_upgrade
  auto_minor_version_upgrade  = var.auto_minor_version_upgrade

  # Instance configuration
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = var.storage_type
  storage_encrypted = var.storage_encrypted
  kms_key_id        = var.storage_encrypted ? aws_kms_key.rds[0].arn : null
  iops              = var.iops

  # Database configuration
  db_name  = var.database_name
  username = var.username
  password = var.create_random_password ? random_password.master[0].result : var.password
  port     = var.port

  # Network configuration
  db_subnet_group_name   = var.create_db_subnet_group ? aws_db_subnet_group.main[0].name : var.db_subnet_group_name
  vpc_security_group_ids = concat([aws_security_group.rds.id], var.vpc_security_group_ids)
  publicly_accessible    = var.publicly_accessible
  multi_az               = var.multi_az

  # Parameter and option groups
  parameter_group_name = aws_db_parameter_group.main.name
  option_group_name    = length(var.options) > 0 ? aws_db_option_group.main[0].name : null

  # Backup configuration
  backup_retention_period = var.backup_retention_period
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window

  # Monitoring configuration
  enabled_cloudwatch_logs_exports       = var.enabled_cloudwatch_logs_exports
  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_enabled ? var.performance_insights_retention_period : null
  monitoring_interval                   = var.monitoring_interval
  monitoring_role_arn                   = var.monitoring_interval > 0 ? (local.create_monitoring_role ? aws_iam_role.enhanced_monitoring[0].arn : var.monitoring_role_arn) : null

  # Other configurations
  ca_cert_identifier          = var.ca_cert_identifier
  apply_immediately           = var.apply_immediately
  deletion_protection         = var.deletion_protection
  skip_final_snapshot         = var.skip_final_snapshot
  final_snapshot_identifier   = var.skip_final_snapshot ? null : "${var.final_snapshot_identifier_prefix}-${var.identifier}-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  lifecycle {
    ignore_changes = [password]
  }

  tags = merge(
    local.common_tags,
    {
      Name = var.identifier
    }
  )
}

# Store password in AWS Secrets Manager
resource "aws_secretsmanager_secret" "rds_password" {
  count = var.create_random_password ? 1 : 0

  name                    = "${var.identifier}-master-password"
  description             = "Master password for RDS instance ${var.identifier}"
  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name = "${var.identifier}-master-password"
    }
  )
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  count = var.create_random_password ? 1 : 0

  secret_id = aws_secretsmanager_secret.rds_password[0].id
  secret_string = jsonencode({
    username = aws_db_instance.main.username
    password = random_password.master[0].result
    engine   = var.engine
    host     = aws_db_instance.main.address
    port     = var.port
    dbname   = var.database_name
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  alarm_name          = "${var.identifier}-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name          = "${var.identifier}-database-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS connection count"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "free_storage_space" {
  alarm_name          = "${var.identifier}-free-storage-space"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "10737418240" # 10GB in bytes
  alarm_description   = "This metric monitors RDS free storage"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}