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

output "inference_lambda_name" {
  description = "Lambda that returns a forecast and anomaly scores for a time window"
  value       = module.ml.inference_lambda_name
}

output "endpoint_names" {
  description = "Serverless endpoint names"
  value       = module.ml.endpoint_names
}

output "params_uri" {
  description = "S3 location of the detector parameters (written by ml.inference.calibrate)"
  value       = module.ml.params_uri
}
