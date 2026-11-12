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

### Local Demo (one command)

```bash
docker compose up
# Frontend → http://localhost:5173   API → http://localhost:8080   DynamoDB Local → http://localhost:8000
```

No AWS credentials needed: the API falls back to local gold CSV exports (if present) or `fixtures/`.

### Local Development (without Docker)

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

# Run dev server (VITE_API_URL defaults to the production API if unset)
VITE_API_URL=http://localhost:8080 npm run dev
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

Normally this is done by GitHub Actions on merge to `main` (see **CI/CD**). Manually:

```powershell
# 1. AWS credentials (SSO access keys in ~/.aws/credentials)
aws sts get-caller-identity

# 2. Build the Lambda package (Terraform deploys infra/build/lambda.zip)
python infra/build/create_lambda_zip.py

# 3. Deploy infrastructure + Lambda code (quote -backend-config / -var-file in PowerShell)
cd infra
terraform init "-backend-config=backend.hcl"
terraform plan "-var-file=terraform.tfvars" "-out=tfplan"
terraform apply tfplan
```

> Lambda code is deployed only through Terraform (old scripts that uploaded code outside Terraform were removed, because the next apply
> would not notice them).

### Test Production
```bash
python scripts/smoke_test.py --api-url https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com --chat
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

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture
- **[infra/README.md](./infra/README.md)** / **[infra/DEPLOYMENT.md](./infra/DEPLOYMENT.md)** - Terraform modules and AWS deployment
- **[infra/github-oidc/](./infra/github-oidc/)** - GitHub Actions OIDC roles
- **[ROADMAP.md](./ROADMAP.md)** - Roadmap

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

GitHub Actions authenticates to AWS with **OIDC** (no access keys in GitHub). Roles are defined in
[`infra/github-oidc/`](infra/github-oidc/) (separate Terraform state):
`g2-greentrack-github-plan` (read-only, PRs) and `g2-greentrack-github-deploy` (main / environments `production`, `e2e`).

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR, push to main | App tests (pytest), local server smoke test, frontend build, `terraform fmt`/`validate` |
| `terraform-plan.yml` | PR touching infra/app | `terraform plan` of production (read-only role, no lock), summary in job |
| `terraform-apply.yml` | push to main (infra/app) | Build Lambda zip → plan → **refuses destroy/replace** → apply → end-to-end smoke test |
| `deploy-frontend.yml` | push to main (app/frontend) | Build with `VITE_API_URL` from Terraform output → S3 sync → CloudFront invalidation |
| `e2e-ephemeral.yml` | manual | Deploys a separate `e2e` stack, smoke test + frontend check, **destroy**, verifies cleanup |
| `data-tests.yml`, `ml-tests.yml`, `genai-tests.yml` | PR | Tests of the other teams |

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
