# Outputs of the ML module. Values: bucket_name, bucket_arn (aws_s3_bucket.ml).

output "bucket_name" {
  description = "S3 bucket for ML training data and artifacts"
  value       = aws_s3_bucket.ml.bucket
}

output "bucket_arn" {
  description = "ARN of the ML bucket, for IAM policies"
  value       = aws_s3_bucket.ml.arn
}
