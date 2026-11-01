from app.backend.common import load_fixture, response


def handler(event, context):
    """GET /anomalies: kthen orët me konsum të çuditshëm."""
    data = load_fixture("anomalies.json")
    return response(200, data)