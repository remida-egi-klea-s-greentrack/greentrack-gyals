# Bootstrap: the S3 bucket that holds Terraform state for this AWS account.
# Variables used: var.region, var.name_prefix, var.environment (see variables.tf).
# data.aws_caller_identity.current supplies the account ID used to make the bucket name unique.

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "greentrack"
      Group       = "g2"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "state" {
  # Bucket names are global across all AWS accounts; the account ID suffix avoids collisions.
  bucket = "${var.name_prefix}-tfstate-${data.aws_caller_identity.current.account_id}"

  # Deleting this bucket would lose every environment's state.
  lifecycle {
    prevent_destroy = true
  }
}

# Keeps old state versions, so a bad apply can be rolled back.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# SSE-S3 encryption: no KMS key, so no monthly key fee.
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
