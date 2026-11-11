from app.backend.common import response


def default_loader():
    """Detect anomalies using Developer B's ML model (log-MAD)."""
    try:
        from app.adapters.ml_anomaly import detect_anomalies
        return detect_anomalies()
    except FileNotFoundError as e:
        print(f"⚠️  ML anomaly data not found: {e}")
        print("📦 Falling back to fixtures/anomalies.json...")
        from app.backend.common import load_fixture
        return load_fixture("anomalies.json")
    except Exception as e:
        print(f"⚠️  Failed to detect anomalies: {e}")
        print("📦 Falling back to fixtures/anomalies.json...")
        from app.backend.common import load_fixture
        return load_fixture("anomalies.json")


def handler(event, context, loader=None):
    """GET /anomalies: kthen orët me konsum të çuditshëm."""
    if loader is None:
        loader = default_loader
    
    data = loader() if callable(loader) else loader
    return response(200, data)