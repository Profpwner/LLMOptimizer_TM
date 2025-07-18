variable "bucket_name" {
  description = "The name of the S3 bucket"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "force_destroy" {
  description = "A boolean that indicates all objects should be deleted from the bucket so that the bucket can be destroyed without error"
  type        = bool
  default     = false
}

variable "versioning_enabled" {
  description = "Enable versioning on the bucket"
  type        = bool
  default     = true
}

variable "lifecycle_rules" {
  description = "List of lifecycle rules to configure"
  type = list(object({
    id      = string
    enabled = bool
    prefix  = string
    
    transition = optional(list(object({
      days          = number
      storage_class = string
    })))
    
    expiration = optional(object({
      days = number
    }))
    
    noncurrent_version_transition = optional(list(object({
      days          = number
      storage_class = string
    })))
    
    noncurrent_version_expiration = optional(object({
      days = number
    }))
  }))
  default = []
}

variable "enable_encryption" {
  description = "Enable default encryption on the bucket"
  type        = bool
  default     = true
}

variable "kms_master_key_id" {
  description = "The AWS KMS master key ID used for the SSE-KMS encryption"
  type        = string
  default     = null
}

variable "block_public_acls" {
  description = "Whether Amazon S3 should block public ACLs for this bucket"
  type        = bool
  default     = true
}

variable "block_public_policy" {
  description = "Whether Amazon S3 should block public bucket policies for this bucket"
  type        = bool
  default     = true
}

variable "ignore_public_acls" {
  description = "Whether Amazon S3 should ignore public ACLs for this bucket"
  type        = bool
  default     = true
}

variable "restrict_public_buckets" {
  description = "Whether Amazon S3 should restrict public bucket policies for this bucket"
  type        = bool
  default     = true
}

variable "cors_rules" {
  description = "List of CORS rules"
  type = list(object({
    allowed_headers = list(string)
    allowed_methods = list(string)
    allowed_origins = list(string)
    expose_headers  = list(string)
    max_age_seconds = number
  }))
  default = []
}

variable "enable_logging" {
  description = "Enable access logging on the bucket"
  type        = bool
  default     = false
}

variable "logging_target_bucket" {
  description = "The name of the bucket that will receive the log objects"
  type        = string
  default     = null
}

variable "logging_target_prefix" {
  description = "A prefix for all log object keys"
  type        = string
  default     = "logs/"
}

variable "enable_intelligent_tiering" {
  description = "Enable S3 Intelligent-Tiering"
  type        = bool
  default     = false
}

variable "intelligent_tiering_days" {
  description = "Number of days for Intelligent-Tiering archive configurations"
  type = object({
    archive_access     = number
    deep_archive_access = number
  })
  default = {
    archive_access     = 90
    deep_archive_access = 180
  }
}

variable "replication_configuration" {
  description = "Map containing cross-region replication configuration"
  type = object({
    role = string
    rules = list(object({
      id       = string
      status   = string
      priority = number
      filter   = optional(object({
        prefix = string
        tags   = map(string)
      }))
      destination = object({
        bucket             = string
        storage_class      = string
        replica_kms_key_id = string
      })
    }))
  })
  default = null
}

variable "enable_object_lock" {
  description = "Enable S3 Object Lock"
  type        = bool
  default     = false
}

variable "object_lock_configuration" {
  description = "Object Lock configuration"
  type = object({
    mode  = string
    days  = number
    years = number
  })
  default = null
}

variable "tags" {
  description = "A mapping of tags to assign to the bucket"
  type        = map(string)
  default     = {}
}

variable "bucket_policy" {
  description = "JSON bucket policy to attach to the bucket"
  type        = string
  default     = null
}

variable "enable_analytics" {
  description = "Enable S3 Analytics"
  type        = bool
  default     = false
}

variable "analytics_configuration" {
  description = "S3 Analytics configuration"
  type = list(object({
    id     = string
    prefix = string
    destination = object({
      bucket_arn = string
      prefix     = string
    })
  }))
  default = []
}

variable "enable_inventory" {
  description = "Enable S3 Inventory"
  type        = bool
  default     = false
}

variable "inventory_configuration" {
  description = "S3 Inventory configuration"
  type = list(object({
    id                     = string
    included_object_versions = string
    schedule_frequency     = string
    destination = object({
      bucket_arn = string
      prefix     = string
      format     = string
    })
  }))
  default = []
}