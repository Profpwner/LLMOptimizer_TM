# ALB Module - Main Configuration

locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = "alb"
    }
  )
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  count = var.create_security_group ? 1 : 0

  name        = "${var.name}-alb-sg"
  description = "Security group for ${var.name} ALB"
  vpc_id      = var.vpc_id

  tags = merge(
    local.common_tags,
    {
      Name = "${var.name}-alb-sg"
    }
  )
}

# Security Group Rules
resource "aws_security_group_rule" "alb_ingress" {
  for_each = var.create_security_group ? { for idx, rule in var.ingress_rules : idx => rule } : {}

  type              = "ingress"
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  protocol          = each.value.protocol
  cidr_blocks       = each.value.cidr_blocks
  description       = each.value.description
  security_group_id = aws_security_group.alb[0].id
}

# Default egress rule
resource "aws_security_group_rule" "alb_egress" {
  count = var.create_security_group ? 1 : 0

  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb[0].id
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = var.name
  internal           = var.internal
  load_balancer_type = var.load_balancer_type
  security_groups    = concat(var.security_groups, var.create_security_group ? [aws_security_group.alb[0].id] : [])
  subnets            = var.subnets

  enable_deletion_protection = var.enable_deletion_protection
  enable_http2               = var.enable_http2
  enable_cross_zone_load_balancing = var.enable_cross_zone_load_balancing
  idle_timeout              = var.idle_timeout
  ip_address_type           = var.ip_address_type
  drop_invalid_header_fields = var.drop_invalid_header_fields

  # Access logs
  dynamic "access_logs" {
    for_each = var.access_logs.enabled ? [1] : []
    content {
      bucket  = var.access_logs.bucket
      prefix  = var.access_logs.prefix
      enabled = var.access_logs.enabled
    }
  }

  tags = merge(
    local.common_tags,
    {
      Name = var.name
    }
  )
}

# Target Groups
resource "aws_lb_target_group" "main" {
  for_each = { for tg in var.target_groups : tg.name => tg }

  name                 = each.value.name
  port                 = each.value.port
  protocol             = each.value.protocol
  vpc_id               = var.vpc_id
  target_type          = each.value.target_type
  deregistration_delay = each.value.deregistration_delay
  slow_start           = each.value.slow_start

  # Health check
  dynamic "health_check" {
    for_each = each.value.health_check != null ? [each.value.health_check] : []
    content {
      enabled             = health_check.value.enabled
      healthy_threshold   = health_check.value.healthy_threshold
      unhealthy_threshold = health_check.value.unhealthy_threshold
      timeout             = health_check.value.timeout
      interval            = health_check.value.interval
      matcher             = health_check.value.matcher
      path                = health_check.value.path
      port                = health_check.value.port
    }
  }

  # Stickiness
  dynamic "stickiness" {
    for_each = each.value.stickiness != null ? [each.value.stickiness] : []
    content {
      enabled         = stickiness.value.enabled
      type            = stickiness.value.type
      cookie_duration = stickiness.value.cookie_duration
      cookie_name     = stickiness.value.cookie_name
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = each.value.name
    }
  )
}

# Listeners
resource "aws_lb_listener" "main" {
  for_each = { for idx, listener in var.listeners : idx => listener }

  load_balancer_arn = aws_lb.main.arn
  port              = each.value.port
  protocol          = each.value.protocol
  certificate_arn   = each.value.certificate_arn
  ssl_policy        = each.value.protocol == "HTTPS" ? coalesce(each.value.ssl_policy, var.ssl_policy) : null

  # Default action
  dynamic "default_action" {
    for_each = [each.value.default_action]
    content {
      type             = default_action.value.type
      target_group_arn = default_action.value.target_group_arn

      # Redirect action
      dynamic "redirect" {
        for_each = default_action.value.redirect != null ? [default_action.value.redirect] : []
        content {
          port        = redirect.value.port
          protocol    = redirect.value.protocol
          status_code = redirect.value.status_code
        }
      }

      # Fixed response action
      dynamic "fixed_response" {
        for_each = default_action.value.fixed_response != null ? [default_action.value.fixed_response] : []
        content {
          content_type = fixed_response.value.content_type
          message_body = fixed_response.value.message_body
          status_code  = fixed_response.value.status_code
        }
      }
    }
  }

  depends_on = [aws_lb_target_group.main]
}

# HTTP to HTTPS redirect listener (common pattern)
resource "aws_lb_listener" "http_redirect" {
  count = var.certificate_arn != null ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# WAF Association
resource "aws_wafv2_web_acl_association" "main" {
  count = var.enable_waf && var.waf_acl_id != null ? 1 : 0

  resource_arn = aws_lb.main.arn
  web_acl_arn  = var.waf_acl_id
}

# Shield Advanced Protection
resource "aws_shield_protection" "main" {
  count = var.enable_shield_advanced ? 1 : 0

  name         = "${var.name}-shield-protection"
  resource_arn = aws_lb.main.arn

  tags = local.common_tags
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "alb_healthy_hosts" {
  for_each = aws_lb_target_group.main

  alarm_name          = "${var.name}-${each.key}-healthy-hosts"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "This metric monitors the number of healthy hosts for ${each.key}"

  dimensions = {
    TargetGroup  = aws_lb_target_group.main[each.key].arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_response_time" {
  alarm_name          = "${var.name}-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "This metric monitors ALB response time"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_4xx_errors" {
  alarm_name          = "${var.name}-4xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HTTPCode_Target_4XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors 4xx errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx_errors" {
  alarm_name          = "${var.name}-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors 5xx errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = local.common_tags
}