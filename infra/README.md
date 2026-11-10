# GreenTrack Infrastructure

Terraform modules for deploying GreenTrack on AWS.

## Architecture

- **DynamoDB**: Two tables with composite keys (household_id + timestamp)
  - `consumption`: Hourly energy consumption data
  - `anomalies`: Detected anomalies
- **Lambda**: Python functions for REST API endpoints
- **API Gateway**: HTTP API for frontend access
- **S3**: Frontend static website hosting

## Prerequisites

1. AWS CLI configured with credentials
2. Terraform >= 1.5.0
3. Confirm group prefix with DataMax team

## Setup

### 1. Bootstrap (First time only)

```bash
cd bootstrap
terraform init
terraform apply -var="group_prefix=g2"  # Use your group number
cd ..
```

### 2. Configure backend

```bash
cp backend.hcl.example backend.hcl
# Edit backend.hcl with your group prefix (e.g., g2-greentrack-terraform-state)
```

### 3. Configure variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
```

### 4. Deploy infrastructure

```bash
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

## Resource Naming

All resources follow the pattern: `{group_prefix}-{project_name}-{environment}-{resource}`

Example for Group 2:
- DynamoDB tables: `g2-greentrack-dev-consumption`, `g2-greentrack-dev-anomalies`
- Lambda functions: `g2-greentrack-dev-consumption`, `g2-greentrack-dev-anomalies`
- S3 bucket (state): `g2-greentrack-terraform-state`

## DynamoDB Schema

### Consumption Table
- **PK (hash_key)**: `household_id` - Identifies the household
- **SK (range_key)**: `timestamp` - ISO 8601 timestamp
- **Attributes**: `global_active_power_kwh`, `sub_metering_*`, etc.

### Anomalies Table
- **PK (hash_key)**: `household_id` - Identifies the household
- **SK (range_key)**: `timestamp` - ISO 8601 timestamp
- **Attributes**: `anomaly_score`, `severity`, `consumption_kwh`

**Query pattern**: `get_by_date_range` now uses Query operation (not Scan):
```python
response = table.query(
    KeyConditionExpression='household_id = :hid AND timestamp BETWEEN :start AND :end',
    ExpressionAttributeValues={':hid': 'house_001', ':start': '2024-01-01', ':end': '2024-01-31'}
)
```

## Lambda Functions

All functions have:
- DynamoDB read/write permissions
- Environment variables:
  - `DYNAMODB_TABLE_CONSUMPTION`
  - `DYNAMODB_TABLE_ANOMALIES`
  - `REGION`
- Automatic code deployment with source code hash tracking

## Default Tags

All resources are tagged with:
- `Project`: GreenTrack
- `ManagedBy`: Terraform
- `Environment`: dev/staging/prod
- `Team`: Group{X}

## Outputs

After deployment:
```bash
terraform output
```

Shows:
- API endpoint URL
- DynamoDB table names
- Lambda function names

## Clean up

```bash
terraform destroy
```

## Notes

- State is stored in S3 with locking via DynamoDB
- All resources use server-side encryption
- DynamoDB has point-in-time recovery enabled
- API Gateway has CORS enabled for frontend access
