from app.backend.common import response


def default_loader():
    """Generate forecast - using fixtures for demo stability."""
    from app.backend.common import load_fixture
    return load_fixture("forecast.json")


def handler(event, context, loader=None):
    """GET /forecast: kthen parashikimin e konsumit."""
    if loader is None:
        loader = default_loader
    
    data = loader() if callable(loader) else loader("forecast.json")
    return response(200, data)