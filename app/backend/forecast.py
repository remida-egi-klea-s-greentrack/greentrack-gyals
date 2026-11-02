from app.backend.common import load_fixture, response


def handler(event, context, loader=load_fixture):
    """GET /forecast: kthen parashikimin e konsumit."""
    data = loader("forecast.json")
    return response(200, data)