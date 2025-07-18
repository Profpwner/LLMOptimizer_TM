output "bucket_id" {
  description = "The name of the bucket"
  value       = aws_s3_bucket.main.id
}

output "bucket_arn" {
  description = "The ARN of the bucket"
  value       = aws_s3_bucket.main.arn
}

output "bucket_domain_name" {
  description = "The bucket domain name"
  value       = aws_s3_bucket.main.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "The bucket region-specific domain name"
  value       = aws_s3_bucket.main.bucket_regional_domain_name
}

output "bucket_hosted_zone_id" {
  description = "The Route 53 Hosted Zone ID for this bucket's region"
  value       = aws_s3_bucket.main.hosted_zone_id
}

output "bucket_region" {
  description = "The AWS region this bucket resides in"
  value       = aws_s3_bucket.main.region
}

output "bucket_website_endpoint" {
  description = "The website endpoint, if the bucket is configured with a website"
  value       = try(aws_s3_bucket.main.website_endpoint, null)
}

output "bucket_website_domain" {
  description = "The domain of the website endpoint, if the bucket is configured with a website"
  value       = try(aws_s3_bucket.main.website_domain, null)
}

output "kms_key_id" {
  description = "The KMS key ID used for bucket encryption"
  value       = var.enable_encryption && var.kms_master_key_id == null ? aws_kms_key.s3[0].id : var.kms_master_key_id
}

output "kms_key_arn" {
  description = "The KMS key ARN used for bucket encryption"
  value       = var.enable_encryption && var.kms_master_key_id == null ? aws_kms_key.s3[0].arn : var.kms_master_key_id
}

output "versioning_enabled" {
  description = "Whether versioning is enabled"
  value       = var.versioning_enabled
}

output "logging_enabled" {
  description = "Whether logging is enabled"
  value       = var.enable_logging
}

output "encryption_enabled" {
  description = "Whether encryption is enabled"
  value       = var.enable_encryption
}

output "object_lock_enabled" {
  description = "Whether object lock is enabled"
  value       = var.enable_object_lock
}

output "intelligent_tiering_enabled" {
  description = "Whether intelligent tiering is enabled"
  value       = var.enable_intelligent_tiering
}

output "replication_enabled" {
  description = "Whether replication is enabled"
  value       = var.replication_configuration != null
}

output "lifecycle_rules_count" {
  description = "Number of lifecycle rules configured"
  value       = length(var.lifecycle_rules) + (var.enable_intelligent_tiering ? 1 : 0)
}

output "cors_rules_count" {
  description = "Number of CORS rules configured"
  value       = length(var.cors_rules)
}

output "public_access_block_configuration" {
  description = "Public access block configuration"
  value = {
    block_public_acls       = var.block_public_acls
    block_public_policy     = var.block_public_policy
    ignore_public_acls      = var.ignore_public_acls
    restrict_public_buckets = var.restrict_public_buckets
  }
}