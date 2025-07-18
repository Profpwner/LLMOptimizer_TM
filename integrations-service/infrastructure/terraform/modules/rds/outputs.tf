output "db_instance_id" {
  description = "The RDS instance ID"
  value       = aws_db_instance.main.id
}

output "db_instance_arn" {
  description = "The ARN of the RDS instance"
  value       = aws_db_instance.main.arn
}

output "db_instance_address" {
  description = "The address of the RDS instance"
  value       = aws_db_instance.main.address
}

output "db_instance_endpoint" {
  description = "The connection endpoint"
  value       = aws_db_instance.main.endpoint
}

output "db_instance_hosted_zone_id" {
  description = "The canonical hosted zone ID of the DB instance (to be used in a Route 53 Alias record)"
  value       = aws_db_instance.main.hosted_zone_id
}

output "db_instance_port" {
  description = "The database port"
  value       = aws_db_instance.main.port
}

output "db_instance_username" {
  description = "The master username for the database"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "db_instance_password" {
  description = "The database password (this password may be old, because Terraform doesn't track it after initial creation)"
  value       = var.create_random_password ? random_password.master[0].result : var.password
  sensitive   = true
}

output "db_instance_database_name" {
  description = "The database name"
  value       = aws_db_instance.main.db_name
}

output "db_subnet_group_id" {
  description = "The db subnet group id"
  value       = var.create_db_subnet_group ? aws_db_subnet_group.main[0].id : var.db_subnet_group_name
}

output "db_parameter_group_id" {
  description = "The db parameter group id"
  value       = aws_db_parameter_group.main.id
}

output "db_option_group_id" {
  description = "The db option group id"
  value       = length(var.options) > 0 ? aws_db_option_group.main[0].id : null
}

output "db_instance_availability_zone" {
  description = "The availability zone of the RDS instance"
  value       = aws_db_instance.main.availability_zone
}

output "db_instance_multi_az" {
  description = "If the RDS instance is multi AZ enabled"
  value       = aws_db_instance.main.multi_az
}

output "db_instance_storage_encrypted" {
  description = "Specifies whether the DB instance is encrypted"
  value       = aws_db_instance.main.storage_encrypted
}

output "db_instance_kms_key_id" {
  description = "The KMS key ID used for encryption"
  value       = var.storage_encrypted ? aws_kms_key.rds[0].id : null
}

output "db_instance_kms_key_arn" {
  description = "The KMS key ARN used for encryption"
  value       = var.storage_encrypted ? aws_kms_key.rds[0].arn : null
}

output "db_instance_ca_cert_identifier" {
  description = "Specifies the identifier of the CA certificate for the DB instance"
  value       = aws_db_instance.main.ca_cert_identifier
}

output "db_instance_status" {
  description = "The RDS instance status"
  value       = aws_db_instance.main.status
}

output "db_instance_security_group_id" {
  description = "The security group ID of the RDS instance"
  value       = aws_security_group.rds.id
}

output "db_instance_monitoring_role_arn" {
  description = "The ARN of the monitoring role"
  value       = local.create_monitoring_role ? aws_iam_role.enhanced_monitoring[0].arn : var.monitoring_role_arn
}

output "db_instance_cloudwatch_log_groups" {
  description = "Map of CloudWatch log groups created for this DB instance"
  value = {
    for log in var.enabled_cloudwatch_logs_exports : log => "/aws/rds/instance/${aws_db_instance.main.id}/${log}"
  }
}

output "secret_arn" {
  description = "The ARN of the secret containing the database credentials"
  value       = var.create_random_password ? aws_secretsmanager_secret.rds_password[0].arn : null
}

output "secret_name" {
  description = "The name of the secret containing the database credentials"
  value       = var.create_random_password ? aws_secretsmanager_secret.rds_password[0].name : null
}

output "connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${aws_db_instance.main.username}:PASSWORD@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
  sensitive   = true
}