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

# Names the assistant (modules/genai) reuses.
output "inference_lambda_arn" {
  description = "ARN of the inference Lambda"
  value       = aws_lambda_function.inference.arn
}

output "gold_database" {
  description = "Glue database of the Gold tables"
  value       = local.gold_database
}

output "athena_workgroup" {
  description = "Athena workgroup with the enforced results location"
  value       = local.athena_workgroup
}

output "gold_bucket_arn" {
  description = "ARN of the Gold bucket"
  value       = data.aws_s3_bucket.gold.arn
}

output "artifacts_bucket_arn" {
  description = "ARN of the bucket holding Athena results"
  value       = data.aws_s3_bucket.artifacts.arn
}

output "pipeline_name" {
  description = "SageMaker forecast pipeline"
  value       = aws_sagemaker_pipeline.forecast.pipeline_name
}

output "model_package_group" {
  description = "Model Registry group of the forecast model"
  value       = aws_sagemaker_model_package_group.forecast.model_package_group_name
}

output "github_pipeline_role_arn" {
  description = "Role the GitHub Actions workflow assumes to start the pipeline"
  value       = aws_iam_role.github_pipeline.arn
}
