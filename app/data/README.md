# DynamoDB Local Setup

Ky folder përmban script-et për setup-in e DynamoDB Local.

## Prerequisites

1. **Nise DynamoDB Local me Docker Compose:**
   ```bash
   docker compose up -d
   ```
   
   DynamoDB Local do të jetë i disponueshëm në `http://localhost:8000`

2. **Instalo dependencies:**
   ```bash
   pip install -r app/requirements.txt
   ```

## Hapat për Setup

### 1. Krijo Tabelat

```bash
python app/data/create_tables.py
```

Kjo krijon:
- `greentrack-consumption` - Tabela për të dhënat e konsumit energjetik
- `greentrack-anomalies` - Tabela për anomalitë e konsumit

### 2. Seed Data

```bash
python app/data/seed_tables.py
```

Kjo mbush tabelat me të dhëna nga `fixtures/`.

## Verifikimi

Për të verifikuar që tabelat janë krijuar:

```bash
aws dynamodb list-tables --endpoint-url http://localhost:8000 --region us-east-1
```

Për të parë të dhënat në një tabelë:

```bash
aws dynamodb scan --table-name greentrack-consumption --endpoint-url http://localhost:8000 --region us-east-1
```

## Teste

Për të nisur testet e database access:

```bash
python -m unittest app.tests.test_database -v
```

## Environment Variables

- `DYNAMODB_ENDPOINT`: Endpoint për DynamoDB (default: `http://localhost:8000`)
- `AWS_REGION`: AWS region (default: `us-east-1`)

Për të përdorur një endpoint tjetër:

```bash
export DYNAMODB_ENDPOINT=http://custom:9000
export AWS_REGION=eu-west-1
python app/data/create_tables.py
```
