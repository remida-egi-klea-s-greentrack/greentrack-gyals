output "table_names" {
  description = "Names of the created tables"
  value       = { for key, table in aws_dynamodb_table.this : key => table.name }
}