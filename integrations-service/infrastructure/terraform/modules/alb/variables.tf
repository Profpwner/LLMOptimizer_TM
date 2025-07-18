variable "name" {
  description = "The name of the ALB"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "internal" {
  description = "If true, the ALB will be internal"
  type        = bool
  default     = false
}

variable "load_balancer_type" {
  description = "The type of load balancer to create. Possible values are application or network"
  type        = string
  default     = "application"
}

variable "vpc_id" {
  description = "VPC ID where the ALB will be deployed"
  type        = string
}

variable "subnets" {
  description = "A list of subnet IDs to attach to the ALB"
  type        = list(string)
}

variable "security_groups" {
  description = "A list of security group IDs to assign to the ALB"
  type        = list(string)
  default     = []
}

variable "enable_deletion_protection" {
  description = "If true, deletion of the load balancer will be disabled via the AWS API"
  type        = bool
  default     = true
}

variable "enable_http2" {
  description = "Indicates whether HTTP/2 is enabled in application load balancers"
  type        = bool
  default     = true
}

variable "enable_cross_zone_load_balancing" {
  description = "Indicates whether cross zone load balancing should be enabled"
  type        = bool
  default     = true
}

variable "idle_timeout" {
  description = "The time in seconds that the connection is allowed to be idle"
  type        = number
  default     = 60
}

variable "ip_address_type" {
  description = "The type of IP addresses used by the subnets for your load balancer. The possible values are ipv4 and dualstack"
  type        = string
  default     = "ipv4"
}

variable "drop_invalid_header_fields" {
  description = "Indicates whether HTTP headers with header fields that are not valid are removed by the load balancer"
  type        = bool
  default     = false
}

variable "access_logs" {
  description = "Access logs configuration"
  type = object({
    enabled = bool
    bucket  = string
    prefix  = string
  })
  default = {
    enabled = false
    bucket  = null
    prefix  = null
  }
}

variable "listeners" {
  description = "List of listener configurations"
  type = list(object({
    port            = number
    protocol        = string
    certificate_arn = optional(string)
    ssl_policy      = optional(string)
    
    default_action = object({
      type             = string
      target_group_arn = optional(string)
      redirect = optional(object({
        port        = string
        protocol    = string
        status_code = string
      }))
      fixed_response = optional(object({
        content_type = string
        message_body = string
        status_code  = string
      }))
    })
  }))
  default = []
}

variable "target_groups" {
  description = "List of target group configurations"
  type = list(object({
    name                 = string
    port                 = number
    protocol             = string
    target_type          = string
    deregistration_delay = optional(number)
    slow_start           = optional(number)
    
    health_check = optional(object({
      enabled             = bool
      healthy_threshold   = number
      unhealthy_threshold = number
      timeout             = number
      interval            = number
      matcher             = string
      path                = string
      port                = string
    }))
    
    stickiness = optional(object({
      enabled         = bool
      type            = string
      cookie_duration = number
      cookie_name     = optional(string)
    }))
  }))
  default = []
}

variable "enable_waf" {
  description = "Enable WAF for the ALB"
  type        = bool
  default     = false
}

variable "waf_acl_id" {
  description = "The ID of the WAF ACL to associate with the ALB"
  type        = string
  default     = null
}

variable "tags" {
  description = "A mapping of tags to assign to the resource"
  type        = map(string)
  default     = {}
}

variable "create_security_group" {
  description = "Whether to create a security group for the ALB"
  type        = bool
  default     = true
}

variable "ingress_rules" {
  description = "List of ingress rules to create"
  type = list(object({
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    description = string
  }))
  default = []
}

variable "certificate_arn" {
  description = "The default SSL certificate ARN for HTTPS listeners"
  type        = string
  default     = null
}

variable "ssl_policy" {
  description = "The name of the SSL Policy for HTTPS listeners"
  type        = string
  default     = "ELBSecurityPolicy-TLS-1-2-2017-01"
}

variable "enable_shield" {
  description = "Enable AWS Shield Standard for the ALB"
  type        = bool
  default     = false
}

variable "enable_shield_advanced" {
  description = "Enable AWS Shield Advanced for the ALB"
  type        = bool
  default     = false
}