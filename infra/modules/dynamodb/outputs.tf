output "table_names" {
  description = "Names of the created tables"
  value       = { for key, table in aws_dynamodb_table.this : key => table.name }
}

output "table_arns" {
  description = "ARNs of the created tables"
  value       = { for key, table in aws_dynamodb_table.this : key => table.arn }
}