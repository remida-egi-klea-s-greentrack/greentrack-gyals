# Remote state for the bootstrap root, stored in the bucket this root creates.
# No variables used: bucket, key, region, use_lockfile and encrypt come from <env>.backend.hcl.
# On the very first run in a new account, rename this file away (see README.md).

terraform {
  backend "s3" {}
}
