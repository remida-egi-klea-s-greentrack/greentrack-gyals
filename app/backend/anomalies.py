from app.backend.common import response


def default_loader(name="anomalies.json"):
    """Anomalitë nga DynamoDB (log-MAD + RCF); fixtures nëse tabela është bosh ose s'arrihet."""
    try:
        from app.adapters.ml_results import load_anomalies
        data = load_anomalies()
        if not data["anomalies"]:
            raise ValueError("anomalies table has no items for household")
        return data
    except Exception as e:
        print(f"Anomalies from DynamoDB failed: {e}; falling back to fixtures")
        from app.backend.common import load_fixture
        return load_fixture(name)


def handler(event, context, loader=None):
    """GET /anomalies: kthen orët me konsum të çuditshëm."""
    if loader is None:
        loader = default_loader

    data = loader() if callable(loader) else loader
    return response(200, data)
