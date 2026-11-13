# Inputs for the ML module.
# Variables:
#   name_prefix   - prefix for resource names (same convention as the other modules)
#   force_destroy - allow deleting the bucket while it still holds objects (true only in a sandbox)

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "force_destroy" {
  description = "Allow destroying the ML bucket even if it is not empty"
  type        = bool
  default     = false
}

# Inference (inference.tf).
#   enable_endpoints            - create the two serverless endpoints (models and configs always exist; they cost nothing)
#   xgboost_image, rcf_image    - built-in algorithm images for this region (same as used for training)
#   xgboost_model_data, rcf_model_data - S3 URIs of the trained model.tar.gz files
#   serverless_memory_mb, serverless_max_concurrency - serverless endpoint size; adjust after measuring

variable "enable_endpoints" {
  description = "Create the serverless XGBoost and RCF endpoints"
  type        = bool
  default     = false
}

variable "xgboost_image" {
  description = "Built-in XGBoost image URI (algorithm mode) for this region"
  type        = string
}

variable "xgboost_model_data" {
  description = "S3 URI of the trained XGBoost model.tar.gz"
  type        = string
}

variable "rcf_image" {
  description = "Built-in Random Cut Forest image URI for this region"
  type        = string
}

variable "rcf_model_data" {
  description = "S3 URI of the trained RCF model.tar.gz"
  type        = string
}

variable "serverless_memory_mb" {
  description = "Memory per serverless endpoint (1024-6144, steps of 1024)"
  type        = number
  default     = 2048
}

variable "serverless_max_concurrency" {
  description = "Maximum concurrent invocations per serverless endpoint"
  type        = number
  default     = 2
}

variable "github_repository" {
  description = "owner/repo whose main-branch workflows may start the forecast pipeline"
  type        = string
  default     = "remida-egi-klea-s-greentrack/greentrack-gyals"
}

variable "github_oidc_sub_prefix" {
  description = "Immutable OIDC subject prefix of the repo (GET /repos/{owner}/{repo}/actions/oidc/customization/sub)"
  type        = string
  default     = "repo:remida-egi-klea-s-greentrack@351971781/greentrack-gyals@1439962229"
}
