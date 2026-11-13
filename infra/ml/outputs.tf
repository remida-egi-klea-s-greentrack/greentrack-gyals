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

output "assistant_lambda_name" {
  description = "Lambda behind /chat and the weekly report"
  value       = module.genai.assistant_lambda_name
}

output "assistant_lambda_arn" {
  description = "ARN of the assistant Lambda"
  value       = module.genai.assistant_lambda_arn
}

output "inference_lambda_arn" {
  description = "ARN of the forecast/anomaly Lambda"
  value       = module.ml.inference_lambda_arn
}

output "pipeline_name" {
  description = "SageMaker forecast pipeline"
  value       = module.ml.pipeline_name
}

output "model_package_group" {
  description = "Model Registry group of the forecast model"
  value       = module.ml.model_package_group
}

output "github_pipeline_role_arn" {
  description = "Role for the ML pipeline workflow (store as the ML_PIPELINE_ROLE_ARN repository secret)"
  value       = module.ml.github_pipeline_role_arn
}
