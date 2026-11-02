from app.backend.common import load_fixture, response


def handler(event, context, loader=load_fixture):
    """GET /anomalies: kthen orët me konsum të çuditshëm."""
    data = loader("anomalies.json")
    return response(200, data)