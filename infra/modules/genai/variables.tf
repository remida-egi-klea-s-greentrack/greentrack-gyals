# Inputs for the GenAI module.
# Variables:
#   name_prefix                     - prefix for resource names
#   model_id                        - Bedrock model or cross-region inference profile id (Claude Haiku)
#   gold_database, athena_workgroup - Gold tables and the workgroup that runs queries (modules/data)
#   gold_bucket_arn, artifacts_bucket_arn - Gold data and Athena results buckets
#   inference_lambda_arn, inference_lambda_name - forecast/anomaly Lambda (modules/ml)

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "model_id" {
  description = "Bedrock model or inference profile id"
  type        = string
  default     = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "gold_database" {
  description = "Glue database of the Gold tables"
  type        = string
}

variable "athena_workgroup" {
  description = "Athena workgroup"
  type        = string
}

variable "gold_bucket_arn" {
  description = "ARN of the Gold bucket"
  type        = string
}

variable "artifacts_bucket_arn" {
  description = "ARN of the bucket holding Athena results"
  type        = string
}

variable "inference_lambda_arn" {
  description = "ARN of the forecast/anomaly Lambda"
  type        = string
}

variable "inference_lambda_name" {
  description = "Name of the forecast/anomaly Lambda"
  type        = string
}
