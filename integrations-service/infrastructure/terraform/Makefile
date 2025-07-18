# Terraform Makefile for LLMOptimizer Infrastructure

.PHONY: help init plan-dev plan-staging plan-prod apply-dev apply-staging apply-prod destroy-dev destroy-staging destroy-prod fmt validate clean

# Default environment
ENV ?= dev

help:
	@echo "Available targets:"
	@echo "  init          - Initialize Terraform"
	@echo "  fmt           - Format Terraform files"
	@echo "  validate      - Validate Terraform configuration"
	@echo "  plan-dev      - Plan changes for development environment"
	@echo "  plan-staging  - Plan changes for staging environment"
	@echo "  plan-prod     - Plan changes for production environment"
	@echo "  apply-dev     - Apply changes to development environment"
	@echo "  apply-staging - Apply changes to staging environment"
	@echo "  apply-prod    - Apply changes to production environment"
	@echo "  destroy-dev   - Destroy development environment"
	@echo "  destroy-staging - Destroy staging environment"
	@echo "  destroy-prod  - Destroy production environment (requires confirmation)"
	@echo "  clean         - Clean up Terraform files"
	@echo "  cost-dev      - Estimate costs for development environment"
	@echo "  cost-staging  - Estimate costs for staging environment"
	@echo "  cost-prod     - Estimate costs for production environment"
	@echo "  output        - Show Terraform outputs"
	@echo "  kubeconfig    - Update kubeconfig for EKS cluster"

init:
	terraform init

fmt:
	terraform fmt -recursive .

validate: fmt
	terraform validate

# Development environment
plan-dev: validate
	terraform plan -var-file=environments/dev.tfvars -out=dev.tfplan

apply-dev: plan-dev
	terraform apply dev.tfplan
	@rm -f dev.tfplan

destroy-dev:
	terraform destroy -var-file=environments/dev.tfvars -auto-approve

# Staging environment
plan-staging: validate
	terraform plan -var-file=environments/staging.tfvars -out=staging.tfplan

apply-staging: plan-staging
	terraform apply staging.tfplan
	@rm -f staging.tfplan

destroy-staging:
	@echo "WARNING: This will destroy the staging environment!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	terraform destroy -var-file=environments/staging.tfvars

# Production environment
plan-prod: validate
	terraform plan -var-file=environments/prod.tfvars -out=prod.tfplan

apply-prod: plan-prod
	@echo "WARNING: You are about to apply changes to PRODUCTION!"
	@echo "Please review the plan carefully."
	@echo "Type 'yes' to continue:"
	@read confirm && [ "$$confirm" = "yes" ] || (echo "Aborted" && exit 1)
	terraform apply prod.tfplan
	@rm -f prod.tfplan

destroy-prod:
	@echo "DANGER: This will destroy the PRODUCTION environment!"
	@echo "This action cannot be undone!"
	@echo "Type 'destroy-production' to continue:"
	@read confirm && [ "$$confirm" = "destroy-production" ] || (echo "Aborted" && exit 1)
	@echo "Disabling deletion protection..."
	terraform apply -var-file=environments/prod.tfvars \
		-var="rds_deletion_protection=false" \
		-var="alb_deletion_protection=false" \
		-auto-approve
	terraform destroy -var-file=environments/prod.tfvars

# Cost estimation (requires infracost CLI)
cost-dev:
	@command -v infracost >/dev/null 2>&1 || { echo "infracost CLI not installed. See: https://www.infracost.io/docs/"; exit 1; }
	infracost breakdown --path . --terraform-var-file environments/dev.tfvars

cost-staging:
	@command -v infracost >/dev/null 2>&1 || { echo "infracost CLI not installed. See: https://www.infracost.io/docs/"; exit 1; }
	infracost breakdown --path . --terraform-var-file environments/staging.tfvars

cost-prod:
	@command -v infracost >/dev/null 2>&1 || { echo "infracost CLI not installed. See: https://www.infracost.io/docs/"; exit 1; }
	infracost breakdown --path . --terraform-var-file environments/prod.tfvars

# Outputs
output:
	@terraform output -json | jq '.'

output-raw:
	@terraform output

# Update kubeconfig
kubeconfig:
	@echo "Updating kubeconfig for EKS cluster..."
	@REGION=$$(terraform output -raw region) && \
	CLUSTER=$$(terraform output -raw eks_cluster_id) && \
	aws eks update-kubeconfig --region $$REGION --name $$CLUSTER

# Get sensitive outputs
get-db-password:
	@SECRET_ARN=$$(terraform output -raw rds_secret_arn) && \
	aws secretsmanager get-secret-value --secret-id $$SECRET_ARN --query 'SecretString' --output text | jq -r '.password'

get-redis-token:
	@SECRET_ARN=$$(terraform output -raw redis_secret_arn) && \
	aws secretsmanager get-secret-value --secret-id $$SECRET_ARN --query 'SecretString' --output text | jq -r '.auth_token'

# Clean up
clean:
	rm -f *.tfplan
	rm -f *.tfstate*
	rm -rf .terraform/

# Workspace management
workspace-list:
	terraform workspace list

workspace-new:
	@read -p "Enter workspace name: " ws_name && \
	terraform workspace new $$ws_name

workspace-select:
	@read -p "Enter workspace name: " ws_name && \
	terraform workspace select $$ws_name

# State management
state-list:
	terraform state list

state-show:
	@read -p "Enter resource address: " resource && \
	terraform state show $$resource

# Import existing resources
import:
	@read -p "Enter resource address: " resource && \
	read -p "Enter resource ID: " id && \
	terraform import $$resource $$id

# Useful aliases
dev: apply-dev
staging: apply-staging
prod: apply-prod

.DEFAULT_GOAL := help