# Variables for bootstrap infrastructure
# Values are provided via .tfvars files (e.g., production.tfvars, sandbox.tfvars)

variable "aws_region" {
  description = "AWS region for the state bucket"
  type        = string
  default     = "eu-central-1"
}

variable "group_prefix" {
  description = "Group prefix (g1, g2, g3, or g4) for shared DataMax account"
  type        = string

  validation {
    condition     = can(regex("^g[1-4]$", var.group_prefix))
    error_message = "Group prefix must be g1, g2, g3, or g4."
  }
}

variable "environment" {
  description = "Environment name (production, sandbox, etc.)"
  type        = string
  default     = "production"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,20}$", var.environment))
    error_message = "Environment must be 3-20 lowercase letters, digits, or hyphens."
  }
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "greentrack"
}
