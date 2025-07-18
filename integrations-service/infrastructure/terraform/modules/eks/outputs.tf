output "cluster_id" {
  description = "The name/id of the EKS cluster"
  value       = aws_eks_cluster.main.id
}

output "cluster_arn" {
  description = "The Amazon Resource Name (ARN) of the cluster"
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_security_group.cluster.id
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN of the EKS cluster"
  value       = aws_iam_role.cluster.arn
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_version" {
  description = "The Kubernetes server version for the cluster"
  value       = aws_eks_cluster.main.version
}

output "cluster_platform_version" {
  description = "The platform version for the cluster"
  value       = aws_eks_cluster.main.platform_version
}

output "node_groups" {
  description = "Map of attribute maps for all EKS node groups created"
  value       = aws_eks_node_group.main
}

output "node_group_iam_role_arn" {
  description = "IAM role ARN of the EKS Node Group"
  value       = aws_iam_role.node_group.arn
}

output "node_group_security_group_id" {
  description = "Security group ID attached to the EKS nodes"
  value       = aws_security_group.node_group.id
}

output "oidc_issuer_url" {
  description = "The URL on the EKS cluster OIDC Issuer"
  value       = try(aws_eks_cluster.main.identity[0].oidc[0].issuer, null)
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC Provider for IRSA"
  value       = try(aws_iam_openid_connect_provider.cluster[0].arn, null)
}

output "cluster_autoscaler_iam_policy_arn" {
  description = "ARN of the Cluster Autoscaler IAM policy"
  value       = try(aws_iam_policy.cluster_autoscaler[0].arn, null)
}

output "aws_load_balancer_controller_iam_policy_arn" {
  description = "ARN of the AWS Load Balancer Controller IAM policy"
  value       = try(aws_iam_policy.aws_load_balancer_controller[0].arn, null)
}

output "external_dns_iam_policy_arn" {
  description = "ARN of the External DNS IAM policy"
  value       = try(aws_iam_policy.external_dns[0].arn, null)
}

output "cert_manager_iam_policy_arn" {
  description = "ARN of the cert-manager IAM policy"
  value       = try(aws_iam_policy.cert_manager[0].arn, null)
}

output "cluster_kms_key_id" {
  description = "The KMS key ID used for cluster encryption"
  value       = aws_kms_key.eks.id
}

output "cluster_kms_key_arn" {
  description = "The KMS key ARN used for cluster encryption"
  value       = aws_kms_key.eks.arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for cluster logs"
  value       = aws_cloudwatch_log_group.eks.name
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --region ${data.aws_region.current.name} --name ${aws_eks_cluster.main.name}"
}

data "aws_region" "current" {}