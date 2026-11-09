# Outputs of the ML root. Values: ml_bucket (module.ml.bucket_name).

output "ml_bucket" {
  description = "S3 bucket for ML training data and artifacts"
  value       = module.ml.bucket_name
}
