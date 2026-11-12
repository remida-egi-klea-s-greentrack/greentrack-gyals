from app.backend.common import response


def default_loader(name="consumption.json"):
    """Load consumption from gold CSV exports, fallback to fixtures."""
    try:
        from app.adapters.gold_loader import load_hourly_consumption
        records = load_hourly_consumption(limit=100)
        if not records:
            raise ValueError("gold export returned no complete hours")
        return {"unit": "kWh", "records": records}
    except Exception as e:
        print(f"⚠️  Failed to load gold data: {e}")
        print("📦 Falling back to fixtures...")
        from app.backend.common import load_fixture
        return load_fixture(name)


def handler(event, context, loader=None):
    """GET /consumption: kthen konsumin orar."""
    if loader is None:
        loader = default_loader

    data = loader("consumption.json")
    return response(200, data)
