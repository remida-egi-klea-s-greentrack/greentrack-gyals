# ML module (Developer B): S3 bucket for training data and model artifacts.
# SageMaker resources (role, registry, pipeline, endpoint) are added here in later steps.
# Variables used: var.name_prefix, var.force_destroy.
# data.aws_caller_identity.current supplies the account ID that keeps the bucket name unique.

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "ml" {
  bucket        = "${var.name_prefix}-ml-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_public_access_block" "ml" {
  bucket                  = aws_s3_bucket.ml.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
