# Bootstrap: Terraform state bucket

Creates one versioned, encrypted, private S3 bucket that stores Terraform state for an AWS account. Every other Terraform root uses this bucket with its own `key`. Run it once per account.

## First run in a new account

The bucket must exist before Terraform can store state in it, so the first apply keeps state locally and then moves it into the bucket.

```bash
cd infra/bootstrap
cp example.tfvars <env>.tfvars              # set region, name_prefix, environment

mv backend.tf backend.tf.off                # 1. no backend yet: local state
terraform init
terraform apply -var-file=<env>.tfvars

mv backend.tf.off backend.tf                # 2. move state into the new bucket
cp example.backend.hcl <env>.backend.hcl    # set bucket = output "state_bucket", region
terraform init -migrate-state -backend-config=<env>.backend.hcl
rm -f terraform.tfstate terraform.tfstate.backup
```

## Later runs

```bash
terraform init -backend-config=<env>.backend.hcl
terraform plan -var-file=<env>.tfvars
```

`sandbox.tfvars` and `sandbox.backend.hcl` are git-ignored because they describe a personal sandbox account.
