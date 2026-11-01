from app.backend.common import load_fixture, response


def handler(event, context):
    """GET /forecast: kthen parashikimin e konsumit."""
    data = load_fixture("forecast.json")
    return response(200, data)