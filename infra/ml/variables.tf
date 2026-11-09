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
