variable "cluster_id" {
  description = "The cluster ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "engine" {
  description = "The name of the cache engine to be used for this cache cluster. Valid values are memcached or redis"
  type        = string
  default     = "redis"
}

variable "engine_version" {
  description = "The version number of the cache engine"
  type        = string
  default     = "7.0"
}

variable "node_type" {
  description = "The instance class to be used"
  type        = string
}

variable "number_cache_nodes" {
  description = "The number of cache nodes that the cache cluster should have"
  type        = number
  default     = 1
}

variable "parameter_group_family" {
  description = "The family of the ElastiCache parameter group"
  type        = string
  default     = "redis7"
}

variable "port" {
  description = "The port number on which each of the cache nodes will accept connections"
  type        = number
  default     = 6379
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs to allow access from"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to connect"
  type        = list(string)
  default     = []
}

variable "automatic_failover_enabled" {
  description = "Specifies whether a read-only replica will be automatically promoted to read/write primary if the existing primary fails"
  type        = bool
  default     = true
}

variable "multi_az_enabled" {
  description = "Specifies whether to enable Multi-AZ Support for the replication group"
  type        = bool
  default     = true
}

variable "at_rest_encryption_enabled" {
  description = "Whether to enable encryption at rest"
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Whether to enable encryption in transit"
  type        = bool
  default     = true
}

variable "auth_token_enabled" {
  description = "Whether to enable AUTH token (password) for Redis"
  type        = bool
  default     = true
}

variable "snapshot_retention_limit" {
  description = "The number of days for which ElastiCache will retain automatic cache cluster snapshots before deleting them"
  type        = number
  default     = 7
}

variable "snapshot_window" {
  description = "The daily time range (in UTC) during which ElastiCache will begin taking a daily snapshot of your cache cluster"
  type        = string
  default     = "03:00-05:00"
}

variable "maintenance_window" {
  description = "The weekly time range for when maintenance on the cache cluster is performed"
  type        = string
  default     = "sun:05:00-sun:06:00"
}

variable "notification_topic_arn" {
  description = "An Amazon Resource Name (ARN) of an SNS topic to send ElastiCache notifications to"
  type        = string
  default     = null
}

variable "apply_immediately" {
  description = "Specifies whether any database modifications are applied immediately, or during the next maintenance window"
  type        = bool
  default     = false
}

variable "auto_minor_version_upgrade" {
  description = "Specifies whether minor version engine upgrades will be applied automatically to the underlying Cache Cluster instances during the maintenance window"
  type        = bool
  default     = true
}

variable "tags" {
  description = "A mapping of tags to assign to the resource"
  type        = map(string)
  default     = {}
}

variable "log_delivery_configuration" {
  description = "Log delivery configuration for the cluster"
  type = list(object({
    destination      = string
    destination_type = string
    log_format       = string
    log_type         = string
  }))
  default = []
}

variable "data_tiering_enabled" {
  description = "Enables data tiering. Data tiering is only supported for replication groups using the r6gd node type"
  type        = bool
  default     = false
}

variable "replicas_per_node_group" {
  description = "Number of replica nodes in each node group"
  type        = number
  default     = 1
}

variable "num_node_groups" {
  description = "Number of node groups (shards) for this Redis replication group"
  type        = number
  default     = 1
}