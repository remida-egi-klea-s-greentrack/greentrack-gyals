output "bucket_names" {
  description = "S3 buckets per layer (bronze, silver, gold, artifacts)"
  value       = { for name, b in aws_s3_bucket.this : name => b.bucket }
}

output "database_names" {
  description = "Glue Data Catalog databases per layer"
  value       = { for layer, db in aws_glue_catalog_database.this : layer => db.name }
}

output "glue_job_names" {
  description = "Glue jobs per pipeline step"
  value       = { for step, job in aws_glue_job.this : step => job.name }
}

output "glue_role_arn" {
  description = "IAM role the Glue jobs run as"
  value       = aws_iam_role.glue.arn
}

output "athena_workgroup" {
  description = "Athena workgroup for SQL queries on the tables"
  value       = aws_athena_workgroup.this.name
}