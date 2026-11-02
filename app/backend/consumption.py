from app.backend.common import load_fixture, response


def handler(event, context, loader=load_fixture):
    """GET /consumption: kthen konsumin orar."""
    data = loader("consumption.json")
    return response(200, data)