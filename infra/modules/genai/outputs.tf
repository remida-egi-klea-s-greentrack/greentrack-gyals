# Outputs of the GenAI module. Values: assistant_lambda_name, assistant_lambda_arn, guardrail_id, guardrail_version, knowledge_base_id, knowledge_base_data_source_id.

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

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base with the energy-saving guidance"
  value       = aws_bedrockagent_knowledge_base.energy.id
}

output "knowledge_base_data_source_id" {
  description = "S3 data source of the Knowledge Base (for start-ingestion-job)"
  value       = aws_bedrockagent_data_source.energy.data_source_id
}
