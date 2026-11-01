from app.backend.common import load_fixture, response


def handler(event, context):
    """GET /consumption: kthen konsumin orar."""
    data = load_fixture("consumption.json")
    return response(200, data)