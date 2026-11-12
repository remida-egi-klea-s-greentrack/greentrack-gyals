# 🚀 GreenTrack AWS Deployment Summary

**Developer C - APP-07 Deployment**  
**Date:** November 12, 2026  
**AWS Account:** cl-eng-internship-2026 (886565871385)  
**Group:** g2  
**Region:** eu-central-1

---

## ✅ Deployment Status: COMPLETE

### 1. **Bootstrap Infrastructure** ✅
- S3 bucket për Terraform state: `g2-greentrack-tfstate-886565871385`
- Versioning enabled
- Encryption: AES256
- Public access blocked
- **Cost:** ~$0.01/month

### 2. **Main Infrastructure** ✅
Deployed via Terraform (`infra/` directory)

#### API Gateway ✅
- **URL:** https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com
- **Type:** HTTP API
- **Region:** eu-central-1
- **Endpoints:**
  - `GET /consumption` - ✅ Working (200 OK)
  - `GET /forecast` - ✅ Working (200 OK)
  - `GET /anomalies` - ✅ Working (200 OK)
  - `POST /chat` - ✅ Working (200 OK)

#### Lambda Functions ✅
All functions deployed with full dependencies (pandas, pyarrow, numpy, etc.)

| Function | Status | Package Size | Runtime |
|----------|--------|--------------|---------|
| `g2-greentrack-production-consumption` | ✅ Active | 85.97 MB | Python 3.11 |
| `g2-greentrack-production-forecast` | ✅ Active | 85.97 MB | Python 3.11 |
| `g2-greentrack-production-anomalies` | ✅ Active | 85.97 MB | Python 3.11 |
| `g2-greentrack-production-chat` | ✅ Active | 85.97 MB | Python 3.11 |

**Note:** Lambda package uploaded to S3 due to size (>50 MB direct upload limit)

#### DynamoDB Tables ✅
| Table | Status | Billing Mode | Items |
|-------|--------|--------------|-------|
| `g2-greentrack-production-consumption` | ✅ Active | On-Demand | 0 |
| `g2-greentrack-production-anomalies` | ✅ Active | On-Demand | 0 |

#### Frontend (S3 + CloudFront) ✅
- **S3 Bucket:** `g2-greentrack-production-frontend-886565871385`
- **CloudFront URL:** https://d2qotsi80vpuyc.cloudfront.net
- **Distribution ID:** E3JZRO92L8GFNV
- **Status:** ✅ Deployed and cached
- **Build:** React production build (626 KB JS)

---

## 📊 Cost Breakdown

### Monthly Costs (Estimated)
| Service | Cost | Notes |
|---------|------|-------|
| **S3 (Terraform state)** | $0.01 | Minimal storage |
| **DynamoDB** | $0.25 | On-demand, minimal usage |
| **Lambda** | $0.20 | Covered by Free Tier (1M requests/month) |
| **API Gateway** | $3.50 | Covered by Free Tier for 12 months |
| **S3 (Frontend)** | $0.50 | Minimal storage |
| **CloudFront** | $1.00 | 50 GB data transfer free/month |
| **TOTAL** | **~$5-6/month** | **~$1-2/month with Free Tier** |

### Free Tier Coverage (First 12 Months)
- ✅ Lambda: 1M requests + 400,000 GB-seconds/month
- ✅ API Gateway: 1M API calls/month
- ✅ CloudFront: 50 GB data transfer + 2M requests/month
- ✅ DynamoDB: 25 GB storage + 25 WCU + 25 RCU

---

## 🛠️ Deployment Scripts Created

### Infrastructure Management
- `infra/bootstrap/production.tfvars` - Bootstrap configuration
- `infra/terraform.tfvars` - Main infrastructure configuration
- `infra/backend.hcl` - Terraform backend configuration

### Build & Deploy Scripts
- `infra/build/create_lambda_zip.py` - Creates Lambda deployment package
- `infra/update-lambdas-s3.ps1` - Updates Lambda functions via S3
- `infra/deploy-frontend.ps1` - Deploys frontend to S3/CloudFront
- `infra/test-api.ps1` - Tests all API endpoints

### Package Structure
```
infra/build/
├── package/          # Lambda dependencies + app code
│   ├── app/         # Application code
│   ├── fixtures/    # Test data
│   ├── pandas/      # Dependencies
│   ├── numpy/
│   ├── pyarrow/
│   └── ...
└── lambda.zip       # Final deployment package (85.97 MB)
```

---

## 🔧 How to Update Deployment

### Update Lambda Functions
```powershell
# 1. Update code in app/ directory
# 2. Rebuild Lambda package
cd infra/build
python create_lambda_zip.py

# 3. Upload to Lambda via S3
cd ..
.\update-lambdas-s3.ps1
```

### Update Frontend
```powershell
# 1. Update code in app/frontend/src/
# 2. Build frontend
cd app/frontend
npm run build

# 3. Deploy to S3/CloudFront
cd ..\..\infra
.\deploy-frontend.ps1
```

### Update Infrastructure
```powershell
# Make changes to Terraform files in infra/
cd infra
terraform plan
terraform apply
```

---

## 🧪 Testing the Deployment

### Test API Endpoints
```powershell
cd infra
.\test-api.ps1
```

### Manual Testing
```bash
# Test consumption
curl https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com/consumption

# Test forecast
curl https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com/forecast

# Test anomalies
curl https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com/anomalies

# Test chat
curl -X POST https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
```

### View Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/g2-greentrack-production-consumption --region eu-central-1 --since 10m --follow
```

---

## 📝 What's Working

### Backend API ✅
- ✅ All 4 endpoints return 200 OK
- ✅ Lambda functions execute successfully
- ✅ Fixtures data loading works
- ✅ CORS configured for frontend access

### Frontend ✅
- ✅ React build successful (626 KB)
- ✅ Deployed to S3
- ✅ CloudFront distribution active
- ✅ API URL configured correctly

### Infrastructure ✅
- ✅ Terraform state in S3
- ✅ All resources created and active
- ✅ IAM roles and policies configured
- ✅ Security groups and networking

---

## 🚧 Known Limitations

### Current Setup
1. **Data Source:** Using fixture files instead of DynamoDB
   - DynamoDB tables are empty (no seeding script run yet)
   - Lambda functions fall back to fixtures automatically

2. **Lambda Package Size:** 85.97 MB
   - Contains full pandas + numpy + pyarrow
   - Must be uploaded via S3 (exceeds 50 MB direct upload limit)
   - Consider Lambda Layers for production optimization

3. **No CI/CD:** Manual deployment via PowerShell scripts
   - APP-08 (GitHub Actions) not yet implemented

### Recommended Improvements
- [ ] Seed DynamoDB tables with actual data
- [ ] Implement Lambda Layers to reduce package size
- [ ] Add monitoring and alerting (CloudWatch Alarms)
- [ ] Implement CI/CD with GitHub Actions (APP-08)
- [ ] Add custom domain name (Route 53 + ACM)
- [ ] Enable WAF for API Gateway
- [ ] Add CloudWatch Dashboards

---

## 🔐 Security Notes

### Implemented
- ✅ S3 bucket public access blocked
- ✅ CloudFront Origin Access Control (OAC)
- ✅ IAM roles with least privilege
- ✅ S3 encryption at rest (AES256)
- ✅ HTTPS only (API Gateway + CloudFront)

### Credentials
- Using AWS SSO with temporary credentials
- No long-term access keys stored
- Session expires automatically

---

## 📚 Documentation References

### Terraform Modules
- `infra/modules/api/` - API Gateway + Lambda
- `infra/modules/dynamodb/` - DynamoDB tables
- `infra/modules/frontend/` - S3 + CloudFront

### Related Files
- `ARCHITECTURE.md` - System architecture
- `CLEANUP_SUMMARY.md` - Project cleanup history
- `app/backend/README.md` - Backend documentation
- `app/frontend/README.md` - Frontend documentation

---

## ✅ APP-07 Completion Checklist

- [x] Terraform bootstrap infrastructure
- [x] Main infrastructure deployment
- [x] Lambda functions with dependencies
- [x] API Gateway endpoints
- [x] DynamoDB tables
- [x] Frontend build
- [x] S3 deployment
- [x] CloudFront distribution
- [x] API testing
- [x] Documentation
- [ ] GitHub Actions CI/CD (APP-08)

---

**Deployed by:** Developer C  
**Completion Date:** November 12, 2026  
**Status:** ✅ Production Ready
