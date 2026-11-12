variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "package_path" {
  description = "Path to the zip file that contains the backend code"
  type        = string
  default     = "../build/lambda.zip"
}

variable "assistant_function_name" {
  description = "Lambda e GenAI assistant-it që shërben POST /chat"
  type        = string
  default     = "g2-greentrack-assistant"
}

variable "household_id" {
  description = "household_id që lexohet nga tabelat forecasts/anomalies"
  type        = string
  default     = "household-1"
}

variable "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs (consumption, anomalies)"
  type        = map(string)
  default     = {}
}