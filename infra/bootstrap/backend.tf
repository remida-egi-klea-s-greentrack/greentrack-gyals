# Remote state for the bootstrap root, stored in the bucket this root creates.
# No variables used: bucket, key, region, use_lockfile and encrypt come from <env>.backend.hcl
# (see backend.hcl.example). On the very first run in a new account, rename this file to
# backend.tf.off, apply with local state, then rename it back and run
# terraform init -migrate-state (README.md, "First run").

terraform {
  backend "s3" {}
}
