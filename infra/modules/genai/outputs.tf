# Outputs of the GenAI module. Values: assistant_lambda_name, assistant_lambda_arn, guardrail_id, guardrail_version.

output "assistant_lambda_name" {
  description = "Lambda behind /chat and the weekly report"
  value       = aws_lambda_function.assistant.function_name
}

output "assistant_lambda_arn" {
  description = "ARN of the assistant Lambda (for lambda:InvokeFunction in the API role)"
  value       = aws_lambda_function.assistant.arn
}

output "guardrail_id" {
  description = "Bedrock guardrail id"
  value       = aws_bedrock_guardrail.assistant.guardrail_id
}

output "guardrail_version" {
  description = "Pinned guardrail version used by the Lambda"
  value       = aws_bedrock_guardrail_version.assistant.version
}
