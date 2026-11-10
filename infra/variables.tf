variable "aws_region" {
  description = "AWS region where resources are created"
  type        = string
  default     = "eu-central-1"
}

variable "group_prefix" {
  description = "Group prefix for resource names (e.g., g2 for group 2)"
  type        = string
  default     = "g2"

  validation {
    condition     = can(regex("^g[0-9]+$", var.group_prefix))
    error_message = "Group prefix must be in format g1, g2, g3, or g4."
  }
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "greentrack"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "default_tags" {
  description = "Default tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "GreenTrack"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}