# Inputs for the bootstrap root. Values differ per AWS account and live in <env>.tfvars.
# Variables:
#   region      - AWS region of the environment (sandbox: eu-north-1, DataMax: eu-central-1)
#   name_prefix - prefix for every resource name (e.g. g2-greentrack in the shared account)
#   environment - value of the Environment tag (e.g. sandbox, datamax)

variable "region" {
  description = "AWS region for this environment"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names: lowercase letters, digits and hyphens"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{3,30}$", var.name_prefix))
    error_message = "name_prefix must be 3-30 characters of lowercase letters, digits or hyphens."
  }
}

variable "environment" {
  description = "Environment name, used as a tag"
  type        = string
}
