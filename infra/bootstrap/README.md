# Terraform Bootstrap Infrastructure

Bootstrap creates the S3 bucket that stores Terraform state for all environments. This is the **first thing you run** in a new AWS account.

## 🎯 What It Creates

- **S3 bucket**: Encrypted, versioned bucket for Terraform state
  - Name: `{group_prefix}-greentrack-tfstate-{account_id}`
  - Features: Versioning, encryption (SSE-S3), public access blocked
  - Safety: `prevent_destroy` lifecycle prevents accidental deletion

## ✨ Enhanced Features (APP-07)

This is an **enhanced version** of the APP-06 bootstrap with:

✅ **S3 Native Locking** (Terraform 1.10+)
- No DynamoDB table needed (cost savings!)
- Uses `use_lockfile = true` in backend config
- Simpler infrastructure, same safety

✅ **Modular Structure**
- Separate files: `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `backend.tf`
- Professional organization

✅ **Multi-Environment Support**
- Production, sandbox, or custom environments
- Environment-specific `.tfvars` files

✅ **Global Uniqueness**
- Bucket name includes AWS account ID
- No collisions with other accounts

✅ **Safety First**
- `prevent_destroy = true` on S3 bucket
- Versioning enabled for state rollback
- Public access blocked

## 📋 Prerequisites

- **Terraform**: >= 1.10.0 (required for S3 native locking)
- **AWS CLI**: Configured with credentials
- **AWS Permissions**: Ability to create S3 buckets

```bash
# Verify Terraform version
terraform version  # Must be >= 1.10.0

# Verify AWS access
aws sts get-caller-identity
```

## 🚀 Usage

### First Run (New AWS Account)

The bootstrap bucket must exist before Terraform can store state in it, so the first run keeps state locally and then migrates it.

#### Step 1: Prepare configuration

```bash
cd infra/bootstrap

# Copy and customize the example
cp production.tfvars.example production.tfvars

# Edit production.tfvars:
# - Set your group_prefix (g1, g2, g3, or g4)
# - Set environment (production, sandbox, etc.)
```

#### Step 2: First apply (local state)

```bash
# Temporarily disable remote backend
mv backend.tf backend.tf.off

# Initialize and create the S3 bucket
terraform init
terraform apply -var-file=production.tfvars
```

**Save the outputs!** You'll need them for the next step:
```
state_bucket = "g2-greentrack-tfstate-123456789012"
```

#### Step 3: Migrate state to S3

```bash
# Create backend configuration
cp backend.hcl.example backend.hcl

# Edit backend.hcl:
# - Set bucket = output from step 2
# - Set region = your AWS region

# Re-enable remote backend
mv backend.tf.off backend.tf

# Migrate state to the newly created bucket
terraform init -migrate-state -backend-config=backend.hcl
```

Now bootstrap's own state is stored in the bucket it created! 🎉

#### Step 4: Clean up local state

```bash
# Remove local state files (now in S3)
rm -f terraform.tfstate terraform.tfstate.backup
```

### Later Runs (Existing Bootstrap)

```bash
cd infra/bootstrap

# Initialize with remote state
terraform init -backend-config=backend.hcl

# Make changes
terraform plan -var-file=production.tfvars
terraform apply -var-file=production.tfvars
```

## 📤 Configure Main Infrastructure

After bootstrap is set up, configure the main infrastructure to use the state bucket:

```bash
cd ../  # Back to infra/

# Copy the backend config example
cp backend.hcl.example backend.hcl

# Edit backend.hcl with bootstrap outputs:
# bucket       = "g2-greentrack-tfstate-123456789012"  # From bootstrap output
# key          = "greentrack/terraform.tfstate"
# region       = "eu-central-1"
# encrypt      = true
# use_lockfile = true  # Terraform 1.10+ native locking

# Initialize main Terraform
terraform init -backend-config=backend.hcl
```

## 🔐 Security Features

1. **Encryption**: SSE-S3 encryption at rest
2. **Versioning**: State history for rollback
3. **Public Access Blocked**: No public exposure
4. **Prevent Destroy**: Cannot accidentally delete bucket
5. **Native Locking**: Prevents concurrent modifications
6. **No DynamoDB**: Simpler, fewer attack surfaces

## 💰 Cost

**Very low:**
- S3 storage: ~$0.023/GB/month
- S3 requests: Minimal (only during Terraform operations)
- **No DynamoDB charges** (eliminated in this version)

Expected: **< $0.50/month** for typical usage

## 🔄 Migration from Old Bootstrap (APP-06)

If you're migrating from the APP-06 bootstrap with DynamoDB:

1. **Upgrade Terraform** to >= 1.10.0
2. **Update backend config** in main infrastructure:
   - Add `use_lockfile = true`
   - Remove `dynamodb_table` parameter
3. **Re-initialize**: `terraform init -reconfigure`
4. **Optional**: Delete old DynamoDB table after verifying everything works

The S3 bucket and state files remain unchanged during migration.

## 🗑️ Cleanup (Dangerous!)

⚠️ **WARNING**: This will delete the state bucket and all Terraform state!

To destroy bootstrap (only do this when tearing down everything):

```bash
cd infra/bootstrap

# First, destroy all other infrastructure that uses this state bucket
# Then:

# Disable prevent_destroy in main.tf temporarily
# Comment out the lifecycle block in aws_s3_bucket.terraform_state

terraform destroy -var-file=production.tfvars
```

## 📊 Resource Naming

Bootstrap creates:
```
{group_prefix}-{project_name}-tfstate-{account_id}
```

Example for Group 2:
```
g2-greentrack-tfstate-123456789012
```

## 🤝 Team Coordination

- **Run bootstrap once per AWS account** (not per developer)
- **Share backend.hcl** with team (bucket name, region)
- **Don't commit** `.tfvars` files with sensitive values to Git
- **production.tfvars** and **backend.hcl** are `.gitignore`d

## 📚 Files

```
bootstrap/
├── main.tf                         # Main bootstrap resources
├── variables.tf                    # Input variables
├── outputs.tf                      # Outputs (bucket name, etc.)
├── versions.tf                     # Terraform version constraints
├── backend.tf                      # Backend config (for bootstrap's own state)
├── README.md                       # This file
├── production.tfvars.example       # Example configuration
├── backend.hcl.example            # Example backend config
└── .gitignore                     # Ignore sensitive files
```

## 🆘 Troubleshooting

### "Error acquiring the state lock"
- Another Terraform process is running
- Wait for it to complete, or use `terraform force-unlock <lock-id>`

### "Bucket name already exists"
- S3 bucket names are globally unique
- The account ID suffix should prevent this
- Check if bucket exists in another region or account

### "Unsupported attribute 'use_lockfile'"
- Upgrade to Terraform >= 1.10.0
- `use_lockfile` is only available in Terraform 1.10+

### "Backend initialization required"
- Run `terraform init -backend-config=backend.hcl`
- Make sure backend.hcl has correct bucket name

## 📞 Support

Issues? Check:
- Terraform version (`terraform version`)
- AWS credentials (`aws sts get-caller-identity`)
- Backend configuration (`backend.hcl` values)

---

**Version**: 2.0 (Enhanced for APP-07)  
**Based on**: APP-06 bootstrap with APP-07 improvements  
**Maintained by**: Developer C (Application & DevOps)
