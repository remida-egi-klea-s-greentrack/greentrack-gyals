# The state bucket in the shared account was created when these resources were named "state".
# These blocks rename them in the Terraform state to "terraform_state"; nothing changes in AWS.
# No variables used. Safe to delete once every environment has applied them.

moved {
  from = aws_s3_bucket.state
  to   = aws_s3_bucket.terraform_state
}

moved {
  from = aws_s3_bucket_versioning.state
  to   = aws_s3_bucket_versioning.terraform_state
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.state
  to   = aws_s3_bucket_server_side_encryption_configuration.terraform_state
}

moved {
  from = aws_s3_bucket_public_access_block.state
  to   = aws_s3_bucket_public_access_block.terraform_state
}
