from app.backend.common import response


def _horizon(event) -> int:
    params = (event or {}).get("queryStringParameters") or {}
    try:
        return max(1, min(int(params.get("horizon_hours", 24)), 168))
    except (TypeError, ValueError):
        return 24


def default_loader(horizon_hours=24):
    """Forecast nga DynamoDB (ML loader); fixtures nëse tabela është bosh ose s'arrihet."""
    try:
        from app.adapters.ml_results import load_forecast
        data = load_forecast(horizon_hours)
        if not data["predictions"]:
            raise ValueError("forecasts table has no items for household")
        return data
    except Exception as e:
        print(f"Forecast from DynamoDB failed: {e}; falling back to fixtures")
        from app.backend.common import load_fixture
        return load_fixture("forecast.json")


def handler(event, context, loader=None):
    """GET /forecast: kthen parashikimin e konsumit."""
    if loader is None:
        data = default_loader(_horizon(event))
    else:
        data = loader("forecast.json")
    return response(200, data)
