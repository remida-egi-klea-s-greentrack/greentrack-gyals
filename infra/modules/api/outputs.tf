output "api_url" {
  description = "Base URL of the HTTP API"
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_apigatewayv2_api.this.id
}

output "lambda_function_arns" {
  description = "ARNs of all Lambda functions"
  value       = { for k, fn in aws_lambda_function.this : k => fn.arn }
}

output "lambda_function_names" {
  description = "Names of all Lambda functions"
  value       = { for k, fn in aws_lambda_function.this : k => fn.function_name }
}