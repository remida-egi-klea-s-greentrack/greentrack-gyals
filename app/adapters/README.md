# Adapters - Data Integration Layer

Ky folder përmban adapter-at që integrojnë punën e Developer A (Data Engineering) dhe Developer B (ML).

## 📁 Modules

### `dynamodb.py`
Repository pattern për DynamoDB access:
- `ConsumptionRepository` - CRUD për konsumim
- `AnomalyRepository` - CRUD për anomali

### `gold_loader.py`
Loader për të dhënat e përpunuara nga Developer A:
- `load_hourly_consumption()` - Konsum orar nga gold layer
- `load_daily_consumption()` - Konsum ditor
- `detect_anomalies_simple()` - Detektim i thjeshtë i anomalive

**Data Source:** `data/lakehouse/exports/gold_*` (Parquet files)

### `ml_forecast.py`
Integrim me modelet ML të Developer B:
- `generate_forecast()` - Gjenerim parashikimi duke përdorur `seasonal_naive_forecast`
- `get_forecast_metadata()` - Info mbi modelin dhe training data

**Model:** `ml/forecasting/baseline.py`

## 🔄 Workflow

```
Developer A                Developer B                 Developer C (Ti)
    │                          │                            │
    ├─ bronze_ingest.py        │                            │
    ├─ silver_clean.py         │                            │
    ├─ gold_aggregate.py ──────┼───> Parquet exports        │
    │                          │                            │
    │                          ├─ baseline.py (model)       │
    │                          │                            │
    │                          │                            ├─ gold_loader.py
    │                          │                            ├─ ml_forecast.py
    │                          │                            │
    └──────────────────────────┴────────────────────────────┴─> REST API handlers
```

## 🚀 Usage

### Në Handler-at

Handler-at përdorin automatikisht gold data me **graceful fallback** te fixtures:

```python
# app/backend/consumption.py
def handler(event, context, loader=None):
    if loader is None:
        loader = default_loader  # Provon gold, fall back te fixtures
    
    data = loader() if callable(loader) else loader("consumption.json")
    return response(200, data)
```

### Direct Usage

```python
from app.adapters.gold_loader import load_hourly_consumption
from app.adapters.ml_forecast import generate_forecast

# Merr konsumim real
records = load_hourly_consumption(limit=100)

# Gjeneroni parashikim ML
predictions = generate_forecast(horizon_hours=24)
```

## ⚙️ Configuration

### Fallback Behavior

Nëse gold data nuk ekziston:
1. Handler-at printojnë warning: `⚠️  Failed to load gold data`
2. Automatikisht kalojnë te fixtures: `📦 Falling back to fixtures...`
3. API vazhdon të funksionojë me mock data

### Prerequisites për Gold Data

Për të përdorur të dhëna reale:

```bash
# 1. Nise PySpark environment (kryer nga Developer A)
python data/jobs/bronze_ingest.py <raw_csv_file>
python data/jobs/silver_clean.py
python data/jobs/gold_aggregate.py

# 2. Verifikoni që exports ekzistojnë
ls data/lakehouse/exports/
```

## 🧪 Testing

```bash
# Teste për integrimin
python -m unittest app.tests.test_gold_integration -v

# Teste për database access
python -m unittest app.tests.test_database -v

# Të gjitha testet
python -m unittest discover app/tests -v
```

## 🎯 Benefits

- **Separation of Concerns**: Çdo developer punon në domain-in e vet
- **Graceful Degradation**: API funksionon edhe pa gold data
- **Testability**: Mock data lejon zhvillim parallel
- **Production Ready**: Thjesht ndrysho environment dhe gold data ngarkohet automatikisht
