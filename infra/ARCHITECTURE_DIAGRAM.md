# GreenTrack AWS Architecture Diagram

## 🏗️ High-Level Architecture

```mermaid
graph TB
    subgraph "External"
        User[👤 Users]
        GitHub[🔧 GitHub Actions<br/>CI/CD]
    end

    subgraph "AWS Cloud - eu-central-1"
        subgraph "Identity & Access"
            OIDC[🔐 OIDC Provider<br/>GitHub Integration]
            IAM[🔑 IAM Roles & Policies]
        end

        subgraph "State Management"
            S3State[(📦 S3 Bucket<br/>Terraform State)]
            DDBLock[(🔒 DynamoDB<br/>State Locking)]
        end

        subgraph "Frontend Layer"
            S3Web[(📁 S3 Bucket<br/>Static Website)]
            CF[☁️ CloudFront<br/>CDN Distribution]
            OAI[🔐 Origin Access<br/>Identity]
        end

        subgraph "API Layer"
            APIGW[🌐 API Gateway<br/>HTTP API]
            subgraph "Lambda Functions"
                L1[⚡ consumption]
                L2[⚡ anomalies]
                L3[⚡ forecast]
                L4[⚡ chat]
            end
        end

        subgraph "Data Layer"
            DDB1[(🗄️ DynamoDB<br/>consumption)]
            DDB2[(🗄️ DynamoDB<br/>anomalies)]
        end

        subgraph "Monitoring"
            CW[📊 CloudWatch<br/>Logs & Metrics]
        end
    end

    %% Connections
    User -->|HTTPS| CF
    CF -->|OAI| S3Web
    User -->|HTTPS| APIGW
    GitHub -->|OIDC Auth| OIDC
    OIDC -.->|Assume Role| IAM
    GitHub -->|Terraform| S3State
    GitHub -->|Lock| DDBLock
    GitHub -->|Deploy| S3Web
    GitHub -->|Deploy| APIGW
    
    APIGW -->|Invoke| L1
    APIGW -->|Invoke| L2
    APIGW -->|Invoke| L3
    APIGW -->|Invoke| L4
    
    L1 -->|Read/Write| DDB1
    L2 -->|Read/Write| DDB2
    L3 -->|Read| DDB1
    L4 -->|Read| DDB1
    
    L1 -.->|Logs| CW
    L2 -.->|Logs| CW
    L3 -.->|Logs| CW
    L4 -.->|Logs| CW
    APIGW -.->|Metrics| CW

    style User fill:#e1f5ff
    style GitHub fill:#ffeaa7
    style S3Web fill:#74b9ff
    style CF fill:#a29bfe
    style APIGW fill:#fd79a8
    style L1 fill:#fdcb6e
    style L2 fill:#fdcb6e
    style L3 fill:#fdcb6e
    style L4 fill:#fdcb6e
    style DDB1 fill:#55efc4
    style DDB2 fill:#55efc4
    style CW fill:#fab1a0
```

---

## 🔄 Data Flow Diagrams

### 1. Frontend Request Flow

```mermaid
sequenceDiagram
    actor User
    participant CF as CloudFront
    participant S3 as S3 Bucket
    participant Browser

    User->>CF: Request https://xxx.cloudfront.net
    CF->>S3: Fetch index.html (via OAI)
    S3-->>CF: Return HTML/JS/CSS
    CF-->>User: Serve cached content
    User->>Browser: Load React App
    Browser->>CF: Fetch static assets
    CF-->>Browser: Serve from edge cache
```

### 2. API Request Flow

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant APIGW as API Gateway
    participant Lambda
    participant DDB as DynamoDB
    participant CW as CloudWatch

    User->>Browser: Click "View Consumption"
    Browser->>APIGW: GET /consumption
    APIGW->>Lambda: Invoke function
    activate Lambda
    Lambda->>DDB: Query consumption table
    DDB-->>Lambda: Return records
    Lambda->>CW: Log request
    Lambda-->>APIGW: Return JSON response
    deactivate Lambda
    APIGW-->>Browser: HTTP 200 + data
    Browser->>User: Display chart
```

### 3. Deployment Flow

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant GH as GitHub
    participant Actions as GitHub Actions
    participant AWS as AWS
    participant S3State as S3 (State)
    participant Lambda
    participant S3Web as S3 (Frontend)
    participant CF as CloudFront

    Dev->>GH: Push to main branch
    GH->>Actions: Trigger workflow
    Actions->>AWS: Authenticate via OIDC
    Actions->>S3State: Read Terraform state
    Actions->>Actions: Build Lambda package
    Actions->>AWS: terraform apply
    AWS->>Lambda: Update functions
    Actions->>Actions: Build React app
    Actions->>S3Web: Upload dist/ files
    Actions->>CF: Invalidate cache
    CF-->>Dev: Deployment complete ✅
```

---

## 📦 Resource Details

### Frontend Resources
- **S3 Bucket:** `{group_prefix}-{project}-{env}-frontend-bucket`
  - Versioning: Disabled
  - Encryption: SSE-S3
  - Public Access: Blocked (CloudFront OAI only)
  
- **CloudFront Distribution:**
  - Origin: S3 bucket via OAI
  - Cache Behavior: Default (TTL: 86400s)
  - Price Class: PriceClass_100 (US, Canada, Europe)
  - SSL: CloudFront certificate (*.cloudfront.net)

### API Resources
- **API Gateway:**
  - Type: HTTP API (v2)
  - CORS: Enabled (CloudFront origin)
  - Stage: $default (auto-deploy)
  
- **Lambda Functions:** (4 functions)
  - Runtime: Python 3.11
  - Memory: 256 MB
  - Timeout: 15 seconds
  - Package: ZIP file (~5-10 MB with dependencies)

### Data Resources
- **DynamoDB Tables:** (2 tables)
  - `consumption`: PK=household_id, SK=timestamp
  - `anomalies`: PK=household_id, SK=timestamp
  - Billing Mode: PAY_PER_REQUEST (on-demand)
  - Point-in-time Recovery: Enabled
  - Encryption: AWS managed keys

### State Management
- **S3 State Bucket:** `{group_prefix}-{project}-tfstate-{account_id}`
  - Versioning: Enabled
  - Encryption: SSE-S3
  - Lifecycle: Prevent destroy
  
- **DynamoDB Lock Table:** `{group_prefix}-{project}-terraform-locks`
  - PK: LockID (String)
  - Billing: PAY_PER_REQUEST

---

## 🔐 Security Architecture

```mermaid
graph TB
    subgraph "IAM Roles & Policies"
        GHRole[GitHub Actions Role<br/>OIDC Federated]
        LambdaRole[Lambda Execution Role]
        
        GHRole -->|Can| TFPerms[Terraform Permissions:<br/>- Manage infrastructure<br/>- Deploy Lambda<br/>- Upload to S3]
        
        LambdaRole -->|Can| LambdaPerms[Lambda Permissions:<br/>- Read/Write DynamoDB<br/>- Write CloudWatch Logs<br/>- Basic execution]
    end

    subgraph "Network Security"
        HTTPS[HTTPS Only<br/>TLS 1.2+]
        CORS[CORS Policy<br/>CloudFront origin]
        OAI[OAI Restricts<br/>S3 access]
    end

    subgraph "Data Security"
        Encrypt[SSE-S3 Encryption<br/>At Rest]
        InTransit[TLS Encryption<br/>In Transit]
    end

    style GHRole fill:#ffeaa7
    style LambdaRole fill:#ffeaa7
    style HTTPS fill:#a29bfe
    style CORS fill:#a29bfe
    style OAI fill:#a29bfe
    style Encrypt fill:#55efc4
    style InTransit fill:#55efc4
```

### Security Best Practices Implemented
✅ No long-lived AWS credentials (OIDC only)  
✅ Least privilege IAM policies  
✅ Encryption at rest (S3, DynamoDB)  
✅ Encryption in transit (HTTPS/TLS)  
✅ S3 public access blocked  
✅ CloudFront Origin Access Identity  
✅ CORS restricted to CloudFront  
✅ CloudWatch logging enabled  
✅ State file encryption and versioning  

---

## 💰 Cost Breakdown

### Estimated Monthly Costs (Low Traffic)

| Service | Usage | Free Tier | Cost |
|---------|-------|-----------|------|
| **Lambda** | 1M requests, 100ms avg | 1M requests/month | ~$0.20 |
| **API Gateway** | 1M requests | 1M messages (12 months) | ~$3.50 |
| **DynamoDB** | 100k reads, 50k writes | 25 GB storage | ~$0.25 |
| **S3** | 5 GB storage + requests | 5 GB (12 months) | ~$0.15 |
| **CloudFront** | 10 GB transfer | 1 TB (12 months) | ~$1.00 |
| **CloudWatch** | Logs 1 GB | 5 GB ingestion | ~$0.50 |
| **State Storage** | S3 + DynamoDB | Covered | ~$0.05 |
| **Total** | | | **~$5-10/month** |

### Cost Optimization Tips
- Use Lambda reserved concurrency for predictable traffic
- DynamoDB on-demand is cheaper for sporadic access
- CloudFront caching reduces origin requests
- CloudWatch log retention policies (7-30 days)
- Delete old Lambda versions

---

## 🔄 Update Scenarios

### Scenario 1: Update Lambda Code
```mermaid
graph LR
    A[Code Change] -->|Push| B[GitHub]
    B -->|Trigger| C[Build Lambda]
    C -->|Package| D[lambda.zip]
    D -->|Terraform| E[Update Lambda]
    E -->|Automatic| F[New Version Live]
```

### Scenario 2: Update Frontend
```mermaid
graph LR
    A[Code Change] -->|Push| B[GitHub]
    B -->|Trigger| C[npm build]
    C -->|Output| D[dist/]
    D -->|aws s3 sync| E[Upload to S3]
    E -->|Invalidate| F[CloudFront Cache]
    F -->|5-10 min| G[New Version Live]
```

### Scenario 3: Infrastructure Change
```mermaid
graph LR
    A[Terraform Edit] -->|PR| B[terraform plan]
    B -->|Review| C[Approve]
    C -->|Merge| D[terraform apply]
    D -->|Update| E[AWS Resources]
    E -->|Test| F[Verify Changes]
```

---

## 📊 Monitoring & Observability

### CloudWatch Dashboards
- API Gateway: Request count, latency, errors
- Lambda: Invocations, duration, errors, throttles
- DynamoDB: Read/write capacity, throttles

### Alarms (To Configure)
- Lambda error rate > 5%
- API Gateway 5xx errors > 10
- DynamoDB throttling events
- CloudFront 5xx error rate

### Logs Retention
- Lambda logs: 7 days (configurable)
- API Gateway logs: 7 days
- CloudTrail: 90 days (governance)

---

## 🚀 Future Enhancements

### Phase 2 (ML Integration)
```mermaid
graph LR
    A[Gold Data] -->|S3| B[ML Bucket]
    B -->|Training| C[SageMaker]
    C -->|Model| D[Endpoint]
    D -->|Inference| E[Lambda]
```

### Phase 3 (GenAI)
```mermaid
graph LR
    A[User Query] -->|Lambda| B[Bedrock]
    B -->|SQL Tool| C[Athena]
    C -->|Query| D[Gold Data]
    D -->|Results| B
    B -->|Answer| A
```

---

**Maintained by:** Developer C (Application & DevOps)  
**Last Updated:** 2026-11-10  
**Version:** 1.0
