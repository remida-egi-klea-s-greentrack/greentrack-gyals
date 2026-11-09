# Example backend settings; copy to <env>.backend.hcl.
# bucket = the state bucket created by infra/bootstrap; key = this root's own state file.

bucket       = "g2-greentrack-tfstate-<ACCOUNT_ID>"
key          = "ml/terraform.tfstate"
region       = "eu-central-1"
use_lockfile = true
encrypt      = true
