# GreenTrack Frontend

Dashboard interaktiv për monitorimin e konsumit të energjisë.

## Quick Start

### 1. Sigurohu që ke të dhënat e nevojshme

Kërkon të dhënat gold nga Developer A dhe ML artifacts nga Developer B.

**Struktura e pritshme:**
```
data/
├── lakehouse/exports/        ← Nga Developer A (Parquet files)
│   ├── gold_hourly_consumption/
│   ├── gold_daily_consumption/
│   └── ...
└── ml_artifacts/             ← Nga Developer B (CSV files)
    ├── anomaly/anomalies.csv
    └── forecasting/predictions.csv
```

### 2. Nis backend-in

```bash
# Nga root e projektit
python -m app.backend.server
```

Backend do të ngarkohet në `http://localhost:8080`

### 3. Nis frontend-in

```bash
# Nga app/frontend/
npm install
npm run dev
```

Frontend do të hapet në `http://localhost:5173`

## Features

- **Konsumi orar:** Shfaq të dhënat nga gold_hourly_consumption (Developer A)
- **Anomalitë:** Shfaq detektimet ML nga Developer B
- **Parashikimet:** Gjeneronanomalies 24-orëshe me seasonal naive model (Developer B)
- **Chat assistant:** Mock për momentin - do të integrohet më vonë
- **Kartela përmbledhëse:** Statistika në kohë reale
- **Grafikë interaktivë:** Recharts për vizualizim

## Teknologjitë

- React 19.3
- Recharts 3.10
- Vite 8.3

## API Endpoints

Frontend lidhet me 4 endpoints në `http://localhost:8080`:

| Endpoint | Metoda | Burimi | Përshkrimi |
|----------|--------|--------|------------|
| `/consumption` | GET | Gold tables (A) | Konsum orar (100 records) |
| `/anomalies` | GET | ML artifacts (B) | Anomalitë e detektuara |
| `/forecast` | GET | ML model (B) | Parashikim 24h |
| `/chat` | POST | Mock | Chat (për t'u implementuar) |

## Struktura

```
app/frontend/
├── src/
│   ├── App.jsx           # Main dashboard component
│   ├── App.css           # Styles
│   └── main.jsx          # Entry point
├── public/               # Static assets
├── package.json          # Dependencies
└── vite.config.js        # Vite configuration
```

## Dokumentimi

Për më shumë detaje:
- `DATA_INTEGRATION_STATUS.md` - Statusi i integrimit
- `CLEANUP_SUMMARY.md` - Pastrimi i projektit
- `test_integration.py` - Integration tests

## Troubleshooting

### Backend nuk niset
```bash
# Instalo dependencies
pip install -r app/requirements.txt

# Testo që të dhënat janë në vend
python test_integration.py
```

### Frontend nuk lidhet me backend
- Sigurohu që backend është në port 8080
- Kontrollo console në browser për CORS errors
- Verifikoni që API endpoint-et kthejnë të dhëna
