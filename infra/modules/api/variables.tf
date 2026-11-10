variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "package_path" {
  description = "Path to the zip file that contains the backend code"
  type        = string
  default     = "../build/lambda.zip"
}

variable "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs (consumption, anomalies)"
  type        = map(string)
  default     = {}
}