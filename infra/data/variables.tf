# Inputs for the data root. Values live in <env>.tfvars.

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