# 🌱 GreenTrack Energy Monitoring System

Real-time energy consumption monitoring and forecasting platform built for AWS.

## 🚀 Quick Links

- **Live Application:** https://d2qotsi80vpuyc.cloudfront.net
- **API Endpoint:** https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com
- **AWS Account:** cl-eng-internship-2026 (886565871385) - Group g2
- **Region:** eu-central-1

## 📋 What's This?

GreenTrack is an energy monitoring dashboard that provides:
- ⚡ Real-time energy consumption tracking
- 📊 24-hour forecasting with ML models
- 🔔 Anomaly detection and alerts
- 💬 AI chat assistant for insights
- 📈 Interactive visualizations

## 🏗️ Architecture

```
Frontend (React) → CloudFront → API Gateway → Lambda Functions → DynamoDB
```

**Tech Stack:**
- **Frontend:** React 19, Recharts, Vite
- **Backend:** Python 3.11, FastAPI-style handlers
- **Infrastructure:** AWS Lambda, API Gateway, DynamoDB, S3, CloudFront
- **IaC:** Terraform
- **CI/CD:** GitHub Actions

## 🎯 Project Structure

```
greentrack-gyals/
├── app/
│   ├── frontend/          # React dashboard
│   ├── backend/           # Lambda handlers
│   ├── adapters/          # Data integration layer
│   └── data/              # DynamoDB utilities
├── infra/                 # Terraform infrastructure
│   ├── modules/           # Reusable modules
│   └── build/             # Lambda package builder
├── data/                  # Data pipeline (Glue/Athena)
├── ml/                    # ML models
├── contracts/             # API contracts
├── fixtures/              # Test data
└── .github/workflows/     # CI/CD pipelines
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- AWS CLI v2
- Terraform 1.5+

### Local Development

#### 1. Backend
```bash
# Install dependencies
pip install -r app/requirements.txt

# Run backend server
python -m app.backend.server
# → http://localhost:8080
```

#### 2. Frontend
```bash
# Install dependencies
cd app/frontend
npm install

# Run dev server
npm run dev
# → http://localhost:5173
```

#### 3. Test API
```bash
# Test consumption
curl http://localhost:8080/consumption

# Test forecast
curl http://localhost:8080/forecast

# Test anomalies
curl http://localhost:8080/anomalies

# Test chat
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
```

## ☁️ AWS Deployment

### Deploy Everything
```powershell
# 1. Set AWS credentials
aws sso login

# 2. Deploy infrastructure
cd infra
terraform init -backend-config=backend.hcl
terraform apply

# 3. Build and deploy Lambda
cd build
python create_lambda_zip.py
cd ..
.\update-lambdas-s3.ps1

# 4. Build and deploy frontend
cd ..\app\frontend
npm run build
cd ..\..\infra
.\deploy-frontend.ps1
```

### Test Production
```powershell
cd infra
.\test-api.ps1
```

### View Logs
```bash
aws logs tail /aws/lambda/g2-greentrack-production-consumption \
  --region eu-central-1 \
  --since 10m \
  --follow
```

## 📊 Cost Estimate

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| Lambda | $0.20 | Free Tier: 1M requests/month |
| API Gateway | $3.50 | Free Tier: 12 months |
| DynamoDB | $0.25 | On-demand, minimal usage |
| S3 + CloudFront | $1.50 | 50 GB transfer free |
| **Total** | **$5-6** | **$1-2 with Free Tier** |

## 🧪 Testing

### Run Tests
```bash
# Backend tests
pytest app/tests/

# Data pipeline tests
pytest data/jobs/tests/

# ML model tests
pytest ml/tests/
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/consumption` | GET | Energy consumption data |
| `/forecast` | GET | 24-hour predictions |
| `/anomalies` | GET | Detected anomalies |
| `/chat` | POST | AI assistant |

### Example Responses

**Consumption:**
```json
{
  "data": [
    {
      "timestamp": "2026-01-01T00:00:00",
      "kwh": 25.5,
      "source": "gold_hourly"
    }
  ]
}
```

**Forecast:**
```json
{
  "predictions": [
    {
      "timestamp": "2026-01-02T00:00:00",
      "kwh": 28.3,
      "confidence": 0.85
    }
  ]
}
```

## 🔧 Configuration

### Environment Variables
```bash
# Backend (optional)
DYNAMODB_ENDPOINT=http://localhost:8000  # For local DynamoDB
AWS_REGION=eu-central-1

# Frontend (build time)
VITE_API_URL=https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com
```

### Terraform Variables
Edit `infra/terraform.tfvars`:
```hcl
project_name = "greentrack"
environment  = "production"
group_id     = "g2"
aws_region   = "eu-central-1"
```

## 📚 Documentation

- **[DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md)** - AWS deployment guide
- **[DEVELOPER_C_COMPLETION_REPORT.md](./DEVELOPER_C_COMPLETION_REPORT.md)** - Full task completion report
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture
- **[CLEANUP_SUMMARY.md](./CLEANUP_SUMMARY.md)** - Project history

## 🤝 Team Structure

- **Developer A:** Data pipeline (Bronze → Silver → Gold)
- **Developer B:** ML models (Forecasting + Anomaly Detection)
- **Developer C:** Backend API + Frontend + AWS Deployment

## 🔐 Security

- ✅ HTTPS only (API Gateway + CloudFront)
- ✅ S3 buckets: Public access blocked
- ✅ CloudFront: Origin Access Control (OAC)
- ✅ IAM: Least privilege roles
- ✅ Encryption: At rest (S3, DynamoDB)
- ✅ AWS SSO: Temporary credentials

## 🐛 Troubleshooting

### Backend won't start
```bash
pip install -r app/requirements.txt
python -m app.backend.server
```

### Frontend API errors
- Check that backend is running on port 8080
- Verify CORS is configured
- Check browser console for errors

### Lambda errors in CloudWatch
```bash
# View logs
aws logs tail /aws/lambda/<function-name> --region eu-central-1 --since 10m

# Common issues:
# - Missing fixtures: Verify fixtures/ directory in Lambda package
# - Import errors: Check dependencies in build/package/
```

### Terraform errors
```bash
# Reinitialize
terraform init -reconfigure

# Refresh state
terraform refresh

# Import existing resources
terraform import <resource_type>.<name> <resource_id>
```

## 📝 CI/CD

GitHub Actions workflows:
- **`ci.yml`** - Validation on PR/push
- **`deploy-frontend.yml`** - Frontend deployment
- **`terraform-apply.yml`** - Infrastructure deployment
- **`data-tests.yml`** - Data pipeline tests
- **`ml-tests.yml`** - ML model tests

**Note:** AWS deployment steps require OIDC configuration (see workflow files for instructions).

## 🚦 Status

| Component | Status | URL |
|-----------|--------|-----|
| Frontend | ✅ Live | https://d2qotsi80vpuyc.cloudfront.net |
| API Gateway | ✅ Live | https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com |
| Lambda Functions | ✅ Active | 4/4 working |
| DynamoDB | ✅ Active | 2 tables |
| CloudFront | ✅ Active | Cache working |

## 📈 Roadmap

### Phase 1: MVP ✅ **COMPLETE**
- [x] Backend REST API
- [x] Frontend dashboard
- [x] AWS infrastructure
- [x] Basic CI/CD

### Phase 2: Data Integration (In Progress)
- [ ] Seed DynamoDB with real data
- [ ] Connect to gold tables
- [ ] Real-time data refresh

### Phase 3: ML Integration
- [ ] Deploy trained models
- [ ] Real-time anomaly detection
- [ ] Improved forecasting

### Phase 4: Production Hardening
- [ ] Custom domain (Route 53)
- [ ] WAF protection
- [ ] Enhanced monitoring
- [ ] Backup strategy

## 🎓 Learning Resources

- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [React Documentation](https://react.dev/)
- [DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/index.html)

## 📞 Support

For questions or issues:
1. Check existing documentation in `docs/` folder
2. Review CloudWatch logs for errors
3. Check GitHub Issues
4. Contact team leads

## 📄 License

Internal project for cl-eng-internship-2026 program.

---

**Built with ❤️ by Team g2**  
**Last Updated:** November 12, 2026
