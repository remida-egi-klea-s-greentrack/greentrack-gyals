# Terraform version, AWS provider and S3 backend for the data stack.

terraform {
  # 1.10+ is required for S3 native state locking (use_lockfile).
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {}
}