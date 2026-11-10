# Main infrastructure outputs

output "api_gateway_url" {
  description = "Base URL for the REST API"
  value       = module.api.api_url
}

output "cloudfront_url" {
  description = "HTTPS URL for the React dashboard"
  value       = module.frontend.cloudfront_url
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidation"
  value       = module.frontend.cloudfront_distribution_id
}

output "frontend_bucket_name" {
  description = "S3 bucket name for frontend deployment"
  value       = module.frontend.bucket_name
}

output "dynamodb_table_names" {
  description = "DynamoDB table names"
  value       = module.dynamodb.table_names
}

output "lambda_function_names" {
  description = "Lambda function names"
  value       = module.api.lambda_function_names
}

output "deployment_info" {
  description = "Quick deployment reference"
  value = {
    api_url         = module.api.api_url
    frontend_url    = module.frontend.cloudfront_url
    frontend_bucket = module.frontend.bucket_name
    region          = var.aws_region
    environment     = var.environment
  }
}
