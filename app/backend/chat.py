import json

from app.backend.common import load_fixture, response


def handler(event, context, loader=load_fixture):
    """POST /chat: kthen përgjigjen e asistentit (e rreme për momentin)."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON"})

    if not body.get("message"):
        return response(400, {"error": "Field 'message' is required"})

    data = loader("chat.json")
    return response(200, data)