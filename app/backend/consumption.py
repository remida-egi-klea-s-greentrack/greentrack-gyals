from app.backend.common import response


def default_loader(name="consumption.json"):
    """Load consumption from the DynamoDB table, then gold CSV exports, then fixtures."""
    try:
        from app.adapters.ml_results import load_consumption
        data = load_consumption(limit=100)
        if data["records"]:
            return data
        print("WARN consumption table is empty; trying gold CSV exports")
    except Exception as e:
        print(f"WARN failed to read consumption table: {e}; trying gold CSV exports")
    try:
        from app.adapters.gold_loader import load_hourly_consumption
        records = load_hourly_consumption(limit=100)
        if not records:
            raise ValueError("gold export returned no complete hours")
        return {"unit": "kWh", "records": records}
    except Exception as e:
        print(f"WARN failed to load gold data: {e}; falling back to fixtures")
        from app.backend.common import load_fixture
        return load_fixture(name)


def handler(event, context, loader=None):
    """GET /consumption: kthen konsumin orar."""
    if loader is None:
        loader = default_loader

    data = loader("consumption.json")
    return response(200, data)
