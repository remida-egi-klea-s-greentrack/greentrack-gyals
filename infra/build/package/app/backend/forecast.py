from app.backend.common import response


def default_loader():
    """Generate forecast using ML model or fallback to fixtures."""
    try:
        from app.adapters.ml_forecast import generate_forecast, get_forecast_metadata
        
        predictions = generate_forecast(horizon_hours=24)
        metadata = get_forecast_metadata()
        
        return {
            "unit": "kWh",
            "horizon_hours": 24,
            "predictions": predictions,
            "model_info": metadata,
        }
    except Exception as e:
        print(f"⚠️  Failed to generate forecast: {e}")
        print("📦 Falling back to fixtures...")
        from app.backend.common import load_fixture
        return load_fixture("forecast.json")


def handler(event, context, loader=None):
    """GET /forecast: kthen parashikimin e konsumit."""
    if loader is None:
        loader = default_loader
    
    data = loader() if callable(loader) else loader("forecast.json")
    return response(200, data)