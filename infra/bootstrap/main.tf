/**
 * Bootstrap infrastructure for Terraform state management
 * 
 * This creates the S3 bucket and DynamoDB table needed for remote state.
 * Run this ONCE before applying main infrastructure:
 *   cd bootstrap
 *   terraform init
 *   terraform apply -var="group_prefix=g2"
 */

variable "group_prefix" {
  description = "Group prefix (g1, g2, g3, or g4)"
  type        = string
  
  validation {
    condition     = can(regex("^g[1-4]$", var.group_prefix))
    error_message = "Group prefix must be g1, g2, g3, or g4."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# S3 bucket for Terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.group_prefix}-greentrack-terraform-state"

  tags = {
    Name        = "${var.group_prefix}-greentrack-terraform-state"
    Purpose     = "Terraform State Storage"
    Project     = "GreenTrack"
    ManagedBy   = "Terraform Bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB table for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${var.group_prefix}-greentrack-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name        = "${var.group_prefix}-greentrack-terraform-locks"
    Purpose     = "Terraform State Locking"
    Project     = "GreenTrack"
    ManagedBy   = "Terraform Bootstrap"
  }
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = aws_dynamodb_table.terraform_locks.id
}

output "backend_config" {
  description = "Backend configuration for main Terraform"
  value = <<-EOT
    bucket         = "${aws_s3_bucket.terraform_state.id}"
    key            = "greentrack/terraform.tfstate"
    region         = "${var.aws_region}"
    dynamodb_table = "${aws_dynamodb_table.terraform_locks.id}"
    encrypt        = true
  EOT
}
