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

output "inference_lambda_name" {
  description = "Lambda that returns a forecast and anomaly scores for a time window"
  value       = aws_lambda_function.inference.function_name
}

output "endpoint_names" {
  description = "Serverless endpoint names (exist only when enable_endpoints = true)"
  value       = local.endpoint_names
}

output "params_uri" {
  description = "Where the calibrate command writes the detector parameters"
  value       = "s3://${aws_s3_bucket.ml.bucket}/${local.params_key}"
}
