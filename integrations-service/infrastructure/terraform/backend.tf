# Backend configuration for remote state
# Uncomment and configure based on your cloud provider

# AWS S3 Backend
# terraform {
#   backend "s3" {
#     bucket         = "llmoptimizer-terraform-state"
#     key            = "infrastructure/terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     dynamodb_table = "llmoptimizer-terraform-lock"
#   }
# }

# GCS Backend
# terraform {
#   backend "gcs" {
#     bucket  = "llmoptimizer-terraform-state"
#     prefix  = "infrastructure"
#   }
# }