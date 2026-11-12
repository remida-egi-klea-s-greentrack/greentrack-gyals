# GreenTrack AWS Deployment Guide

## 🎯 Overview

This guide covers deploying the GreenTrack application to AWS using Terraform. The infrastructure includes:

- **S3 + CloudFront:** Static React frontend hosting
- **Lambda + API Gateway:** Serverless REST API backend
- **DynamoDB:** NoSQL database for consumption and anomaly data
- **IAM:** Least-privilege roles and policies
- **Remote State:** S3 backend with DynamoDB locking

---

## 📋 Prerequisites

### 1. AWS Account Access
- Access to DataMax shared AWS account
- Group prefix assigned (e.g., `g2` for Group 2)
- IAM permissions to create resources
- AWS CLI configured with credentials

### 2. Tools Required
- **Terraform:** >= 1.5.0 ([install](https://developer.hashicorp.com/terraform/install))
- **AWS CLI:** >= 2.0 ([install](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- **Node.js:** >= 18.0 (for frontend build)
- **Python:** 3.11 (for Lambda package)

### 3. Verify Setup
```bash
# Check Terraform
terraform version

# Check AWS CLI
aws --version
aws sts get-caller-identity

# Check Node.js
node --version
npm --version

# Check Python
python --version
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌─────────────────┐                    │
│  │   GitHub     │─────▶│  GitHub Actions │                    │
│  │  Repository  │      │   (OIDC Auth)   │                    │
│  └──────────────┘      └────────┬────────┘                    │
│                                  │                              │
│                                  ▼                              │
│                         ┌─────────────────┐                    │
│                         │   Terraform     │                    │
│                         │  State (S3)     │                    │
│                         └────────┬────────┘                    │
│                                  │                              │
│         ┌────────────────────────┼────────────────────────┐   │
│         │                        │                        │   │
│         ▼                        ▼                        ▼   │
│  ┌─────────────┐        ┌──────────────┐       ┌─────────────┐│
│  │     S3      │        │   Lambda +   │       │  DynamoDB   ││
│  │  (Frontend) │        │ API Gateway  │◀─────▶│   Tables    ││
│  └──────┬──────┘        └──────────────┘       └─────────────┘│
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐                                               │
│  │ CloudFront  │                                               │
│  └──────┬──────┘                                               │
│         │                                                       │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼
     ┌─────────┐
     │  Users  │
     └─────────┘
```

---

## 🚀 Deployment Steps

### Step 1: Bootstrap Infrastructure (First Time Only)

Bootstrap creates the S3 bucket and DynamoDB table for Terraform state management.

```bash
cd infra/bootstrap

# Copy and configure variables
cp example.tfvars production.tfvars

# Edit production.tfvars with your values:
# region      = "eu-central-1"
# name_prefix = "g2-greentrack"  # Use your group prefix
# environment = "production"

# Initialize and apply
terraform init
terraform apply -var-file=production.tfvars
```

**Expected outputs:**
```
s3_bucket_name        = "g2-greentrack-tfstate-123456789"
dynamodb_table_name   = "g2-greentrack-terraform-locks"
backend_config        = "..."
```

**Save these values!** You'll need them for the backend configuration.

---

### Step 2: Configure Backend

Create the backend configuration file:

```bash
cd ../  # Back to infra/

# Copy example
cp backend.hcl.example backend.hcl

# Edit backend.hcl with bootstrap outputs:
# bucket         = "g2-greentrack-tfstate-123456789"
# key            = "greentrack/terraform.tfstate"
# region         = "eu-central-1"
# dynamodb_table = "g2-greentrack-terraform-locks"
# encrypt        = true
```

---

### Step 3: Configure Variables

```bash
# Copy example
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars:
# aws_region   = "eu-central-1"
# group_prefix = "g2"           # Your group number
# project_name = "greentrack"
# environment  = "production"
# 
# default_tags = {
#   Project     = "GreenTrack"
#   ManagedBy   = "Terraform"
#   Environment = "production"
#   Team        = "Group2"      # Your group
# }
```

---

### Step 4: Build Lambda Package

Before deploying, build the Lambda deployment package:

```bash
# From repository root
python infra/build/create_lambda_zip.py
```

This creates `infra/build/lambda.zip` (dependencies from `infra/build/package/` + `app/` + `fixtures/`).
Terraform deploys exactly this file (`package_path` in `infra/main.tf`).

---

### Step 5: Build Frontend

Build the React frontend for production:

```bash
cd app/frontend/

# Install dependencies
npm install

# Build for production
npm run build

# Output is in app/frontend/dist/
```

---

### Step 6: Deploy Infrastructure

```bash
cd infra/

# Initialize with backend
terraform init -backend-config=backend.hcl

# Review planned changes
terraform plan -var-file=terraform.tfvars

# Apply infrastructure
terraform apply -var-file=terraform.tfvars
```

**Expected outputs:**
```
api_gateway_url      = "https://xxx.execute-api.eu-central-1.amazonaws.com"
cloudfront_url       = "https://xxx.cloudfront.net"
dynamodb_table_names = {
  consumption = "g2-greentrack-production-consumption"
  anomalies   = "g2-greentrack-production-anomalies"
}
lambda_function_names = {
  consumption = "g2-greentrack-production-consumption"
  ...
}
```

---

### Step 7: Deploy Frontend to S3

```bash
# Upload frontend build to S3
aws s3 sync app/frontend/dist/ s3://g2-greentrack-production-frontend-bucket/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id EXXXXXXXXXXXXX \
  --paths "/*"
```

---

### Step 8: Test Deployment

```bash
# Test API Gateway
API_URL=$(terraform output -raw api_gateway_url)

curl $API_URL/consumption
curl $API_URL/anomalies
curl $API_URL/forecast
curl -X POST $API_URL/chat -H "Content-Type: application/json" -d '{"message":"What was my peak consumption?"}'

# Test Frontend
open $(terraform output -raw cloudfront_url)
```

---

## 🔄 Update Deployment

Normally: open a PR, merge to `main`, and GitHub Actions deploys (see README → CI/CD).
Manually, when code changes:

```bash
# Rebuild Lambda (from repository root)
python infra/build/create_lambda_zip.py

# Update infrastructure + Lambda code
cd infra/
terraform apply -var-file=terraform.tfvars

# Rebuild and deploy frontend
cd ../app/frontend/
npm run build
aws s3 sync dist/ s3://g2-greentrack-production-frontend-bucket/ --delete
```

---

## 🗑️ Cleanup / Destroy

**⚠️ WARNING:** This will delete all resources and data!

```bash
cd infra/

# Destroy main infrastructure
terraform destroy -var-file=terraform.tfvars

# Optional: Destroy bootstrap (will delete state bucket)
cd bootstrap/
terraform destroy -var-file=production.tfvars
```

---

## 📊 Resource Naming Convention

All resources follow this pattern:
```
{group_prefix}-{project_name}-{environment}-{resource_type}
```

Examples for Group 2:
```
g2-greentrack-production-consumption          # Lambda function
g2-greentrack-production-anomalies            # Lambda function
g2-greentrack-production-api                  # API Gateway
g2-greentrack-production-frontend-bucket      # S3 bucket
g2-greentrack-tfstate-123456789               # State bucket
g2-greentrack-terraform-locks                 # Lock table
```

---

## 🔐 IAM Policies & Least Privilege

### Lambda Execution Role

The Lambda functions have the following permissions:

**Allowed:**
- ✅ Read/Write to DynamoDB tables (consumption, anomalies)
- ✅ Write logs to CloudWatch
- ✅ Basic execution role

**Denied:**
- ❌ S3 access (except ML bucket for Developer B)
- ❌ Secrets Manager (not used yet)
- ❌ Other AWS services

### GitHub Actions Role (OIDC)

**Allowed:**
- ✅ Terraform state (S3, DynamoDB)
- ✅ Create/update/delete infrastructure resources
- ✅ Deploy Lambda functions
- ✅ Upload to S3 frontend bucket

**Denied:**
- ❌ Production data modification
- ❌ IAM user/key creation
- ❌ Billing access

---

## 🔒 Security Best Practices

1. **State Security:**
   - State bucket has encryption enabled (SSE-S3)
   - Versioning enabled for rollback
   - Public access blocked
   - State locking prevents concurrent modifications

2. **Lambda Security:**
   - Environment variables for configuration (not secrets)
   - Least privilege IAM policies
   - VPC deployment not required (public APIs)

3. **Frontend Security:**
   - HTTPS only (CloudFront enforced)
   - S3 bucket not publicly accessible (CloudFront OAI)
   - CORS configured for API domain only

4. **Credentials:**
   - **NEVER** commit AWS credentials to Git
   - Use OIDC for GitHub Actions (no long-lived keys)
   - Use IAM roles, not users

---

## 💰 Cost Estimation

**Expected monthly costs for low-traffic dev/demo:**

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Lambda | 1M requests/month | $0.20 |
| API Gateway | 1M requests/month | $3.50 |
| DynamoDB | On-Demand, 100k reads | $0.25 |
| S3 | 5GB storage + requests | $0.15 |
| CloudFront | 10GB transfer | $1.00 |
| **Total** | | **~$5-10/month** |

**Notes:**
- Free tier covers most Lambda/API Gateway usage
- DynamoDB on-demand pricing (no provisioning)
- CloudFront has 1TB free tier (first 12 months)

---

## 🐛 Troubleshooting

### Terraform Init Fails
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check backend bucket exists
aws s3 ls s3://g2-greentrack-tfstate-123456789/
```

### Lambda Function Error
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/g2-greentrack-production-consumption --follow

# Test function directly
aws lambda invoke \
  --function-name g2-greentrack-production-consumption \
  --payload '{}' \
  response.json
cat response.json
```

### Frontend Not Loading
```bash
# Check S3 bucket
aws s3 ls s3://g2-greentrack-production-frontend-bucket/

# Check CloudFront distribution
aws cloudfront list-distributions
```

### DynamoDB Access Issues
```bash
# Check table exists
aws dynamodb list-tables

# Check IAM role permissions
aws iam get-role-policy \
  --role-name g2-greentrack-production-api-lambda \
  --policy-name g2-greentrack-production-lambda-dynamodb
```

---

## 📚 Additional Resources

- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)

---

## 🤝 Team Coordination

### Before Deployment Checklist
- [ ] Confirm group prefix with team (g1, g2, g3, or g4)
- [ ] Verify AWS account access with DataMax
- [ ] Coordinate with Developer A (data pipeline ready?)
- [ ] Coordinate with Developer B (ML models ready?)
- [ ] Review resource limits and costs
- [ ] Plan deployment window (off-hours recommended)

### After Deployment
- [ ] Share API Gateway URL with team
- [ ] Share CloudFront URL with team
- [ ] Document any issues encountered
- [ ] Update team on resource usage/costs

---

## 📞 Support

**Issues?** Create a GitHub issue with:
- Terraform version
- AWS CLI version
- Error messages
- Steps to reproduce

**Team Contact:**
- Developer A (Data): [Data pipeline, S3, Glue]
- Developer B (ML): [ML models, SageMaker, Bedrock]
- Developer C (You): [Infrastructure, deployment, CI/CD]

---

**Last Updated:** 2026-11-10  
**Version:** 1.0  
**Maintained by:** Developer C (Application & DevOps)
