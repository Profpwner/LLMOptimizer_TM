# S3 Module - Main Configuration

locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = "s3"
    }
  )
}

# KMS key for bucket encryption
resource "aws_kms_key" "s3" {
  count = var.enable_encryption && var.kms_master_key_id == null ? 1 : 0

  description             = "KMS key for ${var.bucket_name} S3 bucket encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${var.bucket_name}-s3-key"
    }
  )
}

resource "aws_kms_alias" "s3" {
  count = var.enable_encryption && var.kms_master_key_id == null ? 1 : 0

  name          = "alias/${var.bucket_name}-s3"
  target_key_id = aws_kms_key.s3[0].key_id
}

# S3 Bucket
resource "aws_s3_bucket" "main" {
  bucket        = var.bucket_name
  force_destroy = var.force_destroy

  # Object Lock must be enabled at bucket creation
  dynamic "object_lock_configuration" {
    for_each = var.enable_object_lock ? [1] : []
    content {
      object_lock_enabled = "Enabled"
    }
  }

  tags = merge(
    local.common_tags,
    {
      Name = var.bucket_name
    }
  )
}

# Bucket Versioning
resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id

  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

# Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  count = var.enable_encryption ? 1 : 0

  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_master_key_id != null || var.enable_encryption ? "aws:kms" : "AES256"
      kms_master_key_id = var.kms_master_key_id != null ? var.kms_master_key_id : aws_kms_key.s3[0].arn
    }
    bucket_key_enabled = true
  }
}

# Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = var.block_public_acls
  block_public_policy     = var.block_public_policy
  ignore_public_acls      = var.ignore_public_acls
  restrict_public_buckets = var.restrict_public_buckets
}

# Bucket Lifecycle Configuration
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  count = length(var.lifecycle_rules) > 0 || var.enable_intelligent_tiering ? 1 : 0

  bucket = aws_s3_bucket.main.id

  # User-defined lifecycle rules
  dynamic "rule" {
    for_each = var.lifecycle_rules
    content {
      id     = rule.value.id
      status = rule.value.enabled ? "Enabled" : "Disabled"

      filter {
        prefix = rule.value.prefix
      }

      dynamic "transition" {
        for_each = rule.value.transition != null ? rule.value.transition : []
        content {
          days          = transition.value.days
          storage_class = transition.value.storage_class
        }
      }

      dynamic "expiration" {
        for_each = rule.value.expiration != null ? [rule.value.expiration] : []
        content {
          days = expiration.value.days
        }
      }

      dynamic "noncurrent_version_transition" {
        for_each = rule.value.noncurrent_version_transition != null ? rule.value.noncurrent_version_transition : []
        content {
          noncurrent_days = noncurrent_version_transition.value.days
          storage_class   = noncurrent_version_transition.value.storage_class
        }
      }

      dynamic "noncurrent_version_expiration" {
        for_each = rule.value.noncurrent_version_expiration != null ? [rule.value.noncurrent_version_expiration] : []
        content {
          noncurrent_days = noncurrent_version_expiration.value.days
        }
      }
    }
  }

  # Intelligent-Tiering rule
  dynamic "rule" {
    for_each = var.enable_intelligent_tiering ? [1] : []
    content {
      id     = "intelligent-tiering"
      status = "Enabled"

      filter {}

      transition {
        days          = 0
        storage_class = "INTELLIGENT_TIERING"
      }
    }
  }
}

# Intelligent-Tiering Configuration
resource "aws_s3_bucket_intelligent_tiering_configuration" "main" {
  count = var.enable_intelligent_tiering ? 1 : 0

  bucket = aws_s3_bucket.main.id
  name   = "${var.bucket_name}-intelligent-tiering"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_days.archive_access
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = var.intelligent_tiering_days.deep_archive_access
  }
}

# CORS Configuration
resource "aws_s3_bucket_cors_configuration" "main" {
  count = length(var.cors_rules) > 0 ? 1 : 0

  bucket = aws_s3_bucket.main.id

  dynamic "cors_rule" {
    for_each = var.cors_rules
    content {
      allowed_headers = cors_rule.value.allowed_headers
      allowed_methods = cors_rule.value.allowed_methods
      allowed_origins = cors_rule.value.allowed_origins
      expose_headers  = cors_rule.value.expose_headers
      max_age_seconds = cors_rule.value.max_age_seconds
    }
  }
}

# Logging Configuration
resource "aws_s3_bucket_logging" "main" {
  count = var.enable_logging ? 1 : 0

  bucket = aws_s3_bucket.main.id

  target_bucket = var.logging_target_bucket
  target_prefix = var.logging_target_prefix
}

# Replication Configuration
resource "aws_s3_bucket_replication_configuration" "main" {
  count = var.replication_configuration != null ? 1 : 0

  role   = var.replication_configuration.role
  bucket = aws_s3_bucket.main.id

  dynamic "rule" {
    for_each = var.replication_configuration.rules
    content {
      id       = rule.value.id
      status   = rule.value.status
      priority = rule.value.priority

      filter {
        prefix = rule.value.filter != null ? rule.value.filter.prefix : ""

        dynamic "tag" {
          for_each = rule.value.filter != null && rule.value.filter.tags != null ? rule.value.filter.tags : {}
          content {
            key   = tag.key
            value = tag.value
          }
        }
      }

      destination {
        bucket             = rule.value.destination.bucket
        storage_class      = rule.value.destination.storage_class
        replica_kms_key_id = rule.value.destination.replica_kms_key_id
      }

      delete_marker_replication {
        status = "Enabled"
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.main]
}

# Object Lock Configuration
resource "aws_s3_bucket_object_lock_configuration" "main" {
  count = var.enable_object_lock && var.object_lock_configuration != null ? 1 : 0

  bucket = aws_s3_bucket.main.id

  rule {
    default_retention {
      mode  = var.object_lock_configuration.mode
      days  = var.object_lock_configuration.days
      years = var.object_lock_configuration.years
    }
  }
}

# Bucket Policy
resource "aws_s3_bucket_policy" "main" {
  count = var.bucket_policy != null ? 1 : 0

  bucket = aws_s3_bucket.main.id
  policy = var.bucket_policy
}

# Analytics Configuration
resource "aws_s3_bucket_analytics_configuration" "main" {
  for_each = { for config in var.analytics_configuration : config.id => config }

  bucket = aws_s3_bucket.main.id
  name   = each.value.id

  filter {
    prefix = each.value.prefix
  }

  storage_class_analysis {
    data_export {
      destination {
        s3_bucket_destination {
          bucket_arn = each.value.destination.bucket_arn
          prefix     = each.value.destination.prefix
        }
      }
    }
  }
}

# Inventory Configuration
resource "aws_s3_bucket_inventory" "main" {
  for_each = { for config in var.inventory_configuration : config.id => config }

  bucket = aws_s3_bucket.main.id
  name   = each.value.id

  included_object_versions = each.value.included_object_versions

  schedule {
    frequency = each.value.schedule_frequency
  }

  destination {
    bucket {
      bucket_arn = each.value.destination.bucket_arn
      prefix     = each.value.destination.prefix
      format     = each.value.destination.format
    }
  }
}

# CloudWatch Metrics
resource "aws_s3_bucket_metric" "main" {
  bucket = aws_s3_bucket.main.id
  name   = "${var.bucket_name}-metrics"
}