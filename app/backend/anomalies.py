import datetime
from app.backend.common import response


def default_loader():
    """Detect anomalies from gold layer or fallback to fixtures."""
    try:
        from app.adapters.gold_loader import detect_anomalies_simple
        anomalies = detect_anomalies_simple(threshold_kwh=5.0)
        return {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "anomalies": anomalies
        }
    except Exception as e:
        print(f"⚠️  Failed to detect anomalies: {e}")
        print("📦 Falling back to fixtures...")
        from app.backend.common import load_fixture
        return load_fixture("anomalies.json")


def handler(event, context, loader=None):
    """GET /anomalies: kthen orët me konsum të çuditshëm."""
    if loader is None:
        loader = default_loader
    
    data = loader() if callable(loader) else loader("anomalies.json")
    return response(200, data)