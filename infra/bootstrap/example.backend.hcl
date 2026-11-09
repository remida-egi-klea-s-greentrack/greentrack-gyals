# Example backend settings; copy to <env>.backend.hcl (sandbox.backend.hcl is git-ignored).
# bucket = output "state_bucket" of the first apply; key = this root's path inside the bucket.

bucket       = "g2-greentrack-tfstate-<ACCOUNT_ID>"
key          = "bootstrap/terraform.tfstate"
region       = "eu-central-1"
use_lockfile = true
encrypt      = true
