output "id" {
  description = "The ID of the ElastiCache cluster or replication group"
  value       = var.engine == "redis" ? aws_elasticache_replication_group.main[0].id : aws_elasticache_cluster.main[0].id
}

output "arn" {
  description = "The ARN of the ElastiCache cluster or replication group"
  value       = var.engine == "redis" ? aws_elasticache_replication_group.main[0].arn : aws_elasticache_cluster.main[0].arn
}

output "primary_endpoint_address" {
  description = "The address of the primary node"
  value = var.engine == "redis" ? (
    var.num_node_groups > 1 ? 
    aws_elasticache_replication_group.main[0].configuration_endpoint_address : 
    aws_elasticache_replication_group.main[0].primary_endpoint_address
  ) : aws_elasticache_cluster.main[0].cluster_address
}

output "configuration_endpoint_address" {
  description = "The configuration endpoint address (for Redis cluster mode)"
  value       = var.engine == "redis" && var.num_node_groups > 1 ? aws_elasticache_replication_group.main[0].configuration_endpoint_address : null
}

output "reader_endpoint_address" {
  description = "The address of the reader endpoint"
  value       = var.engine == "redis" && var.num_node_groups == 1 ? aws_elasticache_replication_group.main[0].reader_endpoint_address : null
}

output "cache_nodes" {
  description = "List of node objects including id, address, port and availability_zone"
  value       = var.engine == "memcached" ? aws_elasticache_cluster.main[0].cache_nodes : []
}

output "port" {
  description = "The port number on which the cache accepts connections"
  value       = var.port
}

output "engine" {
  description = "The engine used"
  value       = var.engine
}

output "engine_version" {
  description = "The engine version used"
  value       = var.engine == "redis" ? aws_elasticache_replication_group.main[0].engine_version_actual : aws_elasticache_cluster.main[0].engine_version
}

output "parameter_group_name" {
  description = "The parameter group name"
  value       = aws_elasticache_parameter_group.main.name
}

output "subnet_group_name" {
  description = "The subnet group name"
  value       = aws_elasticache_subnet_group.main.name
}

output "security_group_id" {
  description = "The security group ID"
  value       = aws_security_group.elasticache.id
}

output "at_rest_encryption_enabled" {
  description = "Whether at-rest encryption is enabled"
  value       = var.at_rest_encryption_enabled
}

output "transit_encryption_enabled" {
  description = "Whether in-transit encryption is enabled"
  value       = var.transit_encryption_enabled
}

output "auth_token_enabled" {
  description = "Whether AUTH token is enabled"
  value       = var.auth_token_enabled && var.transit_encryption_enabled
}

output "kms_key_id" {
  description = "The KMS key ID used for encryption"
  value       = var.at_rest_encryption_enabled ? aws_kms_key.elasticache[0].id : null
}

output "kms_key_arn" {
  description = "The KMS key ARN used for encryption"
  value       = var.at_rest_encryption_enabled ? aws_kms_key.elasticache[0].arn : null
}

output "secret_arn" {
  description = "The ARN of the secret containing the auth token"
  value       = var.auth_token_enabled && var.transit_encryption_enabled && var.engine == "redis" ? aws_secretsmanager_secret.elasticache_auth[0].arn : null
}

output "secret_name" {
  description = "The name of the secret containing the auth token"
  value       = var.auth_token_enabled && var.transit_encryption_enabled && var.engine == "redis" ? aws_secretsmanager_secret.elasticache_auth[0].name : null
}

output "member_clusters" {
  description = "List of member clusters for Redis replication group"
  value       = var.engine == "redis" ? aws_elasticache_replication_group.main[0].member_clusters : []
}

output "num_cache_nodes" {
  description = "The number of cache nodes"
  value       = var.engine == "redis" ? length(aws_elasticache_replication_group.main[0].member_clusters) : var.number_cache_nodes
}

output "cluster_mode_enabled" {
  description = "Indicates if cluster mode is enabled"
  value       = local.cluster_mode_enabled
}

output "redis_connection_string" {
  description = "Redis connection string (without auth token)"
  value       = var.engine == "redis" ? "redis://${var.num_node_groups > 1 ? aws_elasticache_replication_group.main[0].configuration_endpoint_address : aws_elasticache_replication_group.main[0].primary_endpoint_address}:${var.port}" : null
}

output "redis_connection_string_tls" {
  description = "Redis TLS connection string (without auth token)"
  value       = var.engine == "redis" && var.transit_encryption_enabled ? "rediss://${var.num_node_groups > 1 ? aws_elasticache_replication_group.main[0].configuration_endpoint_address : aws_elasticache_replication_group.main[0].primary_endpoint_address}:${var.port}" : null
}