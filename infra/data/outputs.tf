# Names of what this root created.

output "bucket_names" {
  value = module.data.bucket_names
}

output "database_names" {
  value = module.data.database_names
}

output "glue_job_names" {
  value = module.data.glue_job_names
}

output "athena_workgroup" {
  value = module.data.athena_workgroup
}


output "state_machine_arn" {
  value = module.data.state_machine_arn
}