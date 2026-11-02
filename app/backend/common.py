import json
from pathlib import Path

# Folderi fixtures ndodhet dy nivele mbi këtë skedar
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def load_fixture(name):
    """Lexon një skedar JSON nga folderi fixtures."""
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def response(status_code, body):
    """Formati që pret AWS Lambda / API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
    import json
from pathlib import Path

# Folderi fixtures ndodhet dy nivele mbi këtë skedar
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def load_fixture(name):
    """Lexon një skedar JSON nga folderi fixtures."""
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def response(status_code, body):
    """Formati që pret AWS Lambda / API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }