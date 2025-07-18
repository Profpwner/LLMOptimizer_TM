output "lb_id" {
  description = "The ID and ARN of the load balancer"
  value       = aws_lb.main.id
}

output "lb_arn" {
  description = "The ARN of the load balancer"
  value       = aws_lb.main.arn
}

output "lb_dns_name" {
  description = "The DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "lb_zone_id" {
  description = "The canonical hosted zone ID of the load balancer"
  value       = aws_lb.main.zone_id
}

output "lb_arn_suffix" {
  description = "ARN suffix of the load balancer for use with CloudWatch Metrics"
  value       = aws_lb.main.arn_suffix
}

output "security_group_id" {
  description = "The ID of the security group created for the load balancer"
  value       = var.create_security_group ? aws_security_group.alb[0].id : null
}

output "target_group_arns" {
  description = "ARNs of the target groups"
  value       = { for k, v in aws_lb_target_group.main : k => v.arn }
}

output "target_group_arn_suffixes" {
  description = "ARN suffixes of the target groups for use with CloudWatch Metrics"
  value       = { for k, v in aws_lb_target_group.main : k => v.arn_suffix }
}

output "target_group_names" {
  description = "Names of the target groups"
  value       = { for k, v in aws_lb_target_group.main : k => v.name }
}

output "listener_arns" {
  description = "ARNs of the listeners"
  value       = { for k, v in aws_lb_listener.main : k => v.arn }
}

output "listener_ids" {
  description = "IDs of the listeners"
  value       = { for k, v in aws_lb_listener.main : k => v.id }
}

output "http_redirect_listener_arn" {
  description = "ARN of the HTTP to HTTPS redirect listener"
  value       = try(aws_lb_listener.http_redirect[0].arn, null)
}

output "http_redirect_listener_id" {
  description = "ID of the HTTP to HTTPS redirect listener"
  value       = try(aws_lb_listener.http_redirect[0].id, null)
}

output "waf_association_id" {
  description = "ID of the WAF association"
  value       = try(aws_wafv2_web_acl_association.main[0].id, null)
}

output "shield_protection_id" {
  description = "ID of the Shield Advanced protection"
  value       = try(aws_shield_protection.main[0].id, null)
}

output "cloudwatch_metric_alarms" {
  description = "Map of CloudWatch metric alarms"
  value = {
    healthy_hosts = { for k, v in aws_cloudwatch_metric_alarm.alb_healthy_hosts : k => v.id }
    response_time = aws_cloudwatch_metric_alarm.alb_response_time.id
    errors_4xx    = aws_cloudwatch_metric_alarm.alb_4xx_errors.id
    errors_5xx    = aws_cloudwatch_metric_alarm.alb_5xx_errors.id
  }
}