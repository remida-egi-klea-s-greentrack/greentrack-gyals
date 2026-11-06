from app.backend.common import response


def default_loader():
    """Detect anomalies using Developer B's ML model."""
    from app.adapters.ml_anomaly import detect_anomalies
    return detect_anomalies()


def handler(event, context, loader=None):
    """GET /anomalies: kthen orët me konsum të çuditshëm."""
    if loader is None:
        loader = default_loader
    
    data = loader() if callable(loader) else loader
    return response(200, data)