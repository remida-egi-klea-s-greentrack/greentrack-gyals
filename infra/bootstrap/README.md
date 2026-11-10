# Terraform Bootstrap

This directory contains the bootstrap infrastructure needed for Terraform state management.

## What it does

Creates:
- **S3 bucket**: Stores Terraform state files securely with versioning and encryption
- **DynamoDB table**: Provides state locking to prevent concurrent modifications

## Usage

### 1. Bootstrap the infrastructure (ONCE per group)

```bash
cd infra/bootstrap
terraform init
terraform apply -var="group_prefix=g2"  # Change g2 to your group (g1, g2, g3, or g4)
```

This will create:
- S3 bucket: `g2-greentrack-terraform-state`
- DynamoDB table: `g2-greentrack-terraform-locks`

### 2. Configure main Terraform

Copy the backend configuration output and create `infra/backend.hcl`:

```bash
cd ../
cp backend.hcl.example backend.hcl
# Edit backend.hcl with your group prefix
```

### 3. Initialize main infrastructure

```bash
terraform init -backend-config=backend.hcl
```

## Important Notes

- Run bootstrap **only once** per group/account
- The bootstrap state is stored **locally** (bootstrap/terraform.tfstate)
- Keep bootstrap state safe - it's needed to manage the S3 bucket and DynamoDB table
- After bootstrap, all main infrastructure state is stored in S3

## Cleanup

To destroy bootstrap infrastructure (WARNING: this will delete state storage):

```bash
cd infra/bootstrap
terraform destroy -var="group_prefix=g2"
```
