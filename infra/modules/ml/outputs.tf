# Outputs of the ML module. Values: bucket_name, bucket_arn (aws_s3_bucket.ml),
# sagemaker_role_arn (aws_iam_role.sagemaker).

output "bucket_name" {
  description = "S3 bucket for ML training data and artifacts"
  value       = aws_s3_bucket.ml.bucket
}

output "bucket_arn" {
  description = "ARN of the ML bucket, for IAM policies"
  value       = aws_s3_bucket.ml.arn
}

output "sagemaker_role_arn" {
  description = "Execution role for SageMaker processing, training and endpoints"
  value       = aws_iam_role.sagemaker.arn
}
