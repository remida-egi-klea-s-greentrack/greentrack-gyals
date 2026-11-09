# Outputs of the ML root. Values: ml_bucket (module.ml.bucket_name),
# sagemaker_role_arn (module.ml.sagemaker_role_arn).

output "ml_bucket" {
  description = "S3 bucket for ML training data and artifacts"
  value       = module.ml.bucket_name
}

output "sagemaker_role_arn" {
  description = "Execution role for SageMaker jobs"
  value       = module.ml.sagemaker_role_arn
}
