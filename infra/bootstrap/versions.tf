# Terraform and provider versions for the bootstrap root.
# No variables used here. The S3 backend is configured per environment at init time
# (terraform init -backend-config=<env>.backend.hcl); see README.md for the first-run order.

terraform {
  # 1.10+ is required for S3 native state locking (use_lockfile), so no DynamoDB lock table is needed.
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
