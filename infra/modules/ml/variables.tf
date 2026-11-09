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
