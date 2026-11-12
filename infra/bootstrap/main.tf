/**
 * Bootstrap infrastructure for Terraform remote state management
 * 
 * Enhanced version with:
 * - S3 native locking (Terraform 1.10+, no DynamoDB needed)
 * - prevent_destroy lifecycle for safety
 * - Multi-environment support
 * - Account ID in bucket name for global uniqueness
 * 
 * Usage:
 *   cd infra/bootstrap
 *   terraform init
 *   terraform apply -var-file=production.tfvars
 * 
 * Based on: APP-06 with enhancements for APP-07
 */

# Get current AWS account ID for unique bucket naming
data "aws_caller_identity" "current" {}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Group       = var.group_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "terraform-state"
    }
  }
}

# S3 bucket for Terraform state
# Bucket name includes account ID to ensure global uniqueness
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.group_prefix}-${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"

  # Prevent accidental deletion of the state bucket
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "${var.group_prefix}-${var.project_name}-terraform-state"
  }
}

# Enable versioning for state history and rollback capability
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption using S3-managed keys (SSE-S3)
# No KMS key needed, lower cost
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access to the state bucket
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# NOTE: DynamoDB table removed!
# Terraform 1.10+ has native S3 locking via 'use_lockfile = true'
# This eliminates the need for a separate DynamoDB table, reducing cost
# and simplifying infrastructure.
#
# Migration from old DynamoDB-based locking:
# 1. Upgrade to Terraform 1.10+
# 2. Update backend config to use 'use_lockfile = true'
# 3. Remove 'dynamodb_table' parameter from backend config
# 4. The old DynamoDB table can be safely deleted after migration
