# Outputs of the bootstrap root, used to fill in <env>.backend.hcl for every Terraform root.
# Values: state_bucket (bucket name), region (var.region).

output "state_bucket" {
  description = "S3 bucket for Terraform state"
  value       = aws_s3_bucket.state.bucket
}

output "region" {
  description = "Region of the state bucket"
  value       = var.region
}
