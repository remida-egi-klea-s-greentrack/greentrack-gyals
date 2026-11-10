output "bucket_name" {
  description = "S3 bucket that holds the built frontend"
  value       = aws_s3_bucket.site.bucket
}

output "cloudfront_domain" {
  description = "HTTPS address of the dashboard"
  value       = aws_cloudfront_distribution.site.domain_name
}