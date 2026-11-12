# Inputs for the standalone ML root. Values live in <env>.tfvars.
# Variables:
#   region        - AWS region of the environment
#   name_prefix   - prefix for resource names, passed to modules/ml
#   environment   - value of the Environment tag
#   force_destroy - passed to modules/ml (true only in a sandbox)

variable "region" {
  description = "AWS region for this environment"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name, used as a tag"
  type        = string
}

variable "force_destroy" {
  description = "Allow destroying non-empty buckets (sandbox only)"
  type        = bool
  default     = false
}

# Inference (passed to modules/ml):
#   enable_endpoints              - create the serverless endpoints
#   xgboost_image, rcf_image      - built-in algorithm images for the region
#   xgboost_model_data, rcf_model_data - S3 URIs of the trained models

variable "enable_endpoints" {
  description = "Create the serverless XGBoost and RCF endpoints"
  type        = bool
  default     = false
}

variable "xgboost_image" {
  description = "Built-in XGBoost image URI (algorithm mode)"
  type        = string
}

variable "xgboost_model_data" {
  description = "S3 URI of the trained XGBoost model.tar.gz"
  type        = string
}

variable "rcf_image" {
  description = "Built-in Random Cut Forest image URI"
  type        = string
}

variable "rcf_model_data" {
  description = "S3 URI of the trained RCF model.tar.gz"
  type        = string
}
