import json
from pathlib import Path

from app.adapters.config import load_ssm_config

# Every handler imports this module first, so the SSM configuration is in os.environ
# before any adapter reads it (once per Lambda container).
load_ssm_config()

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
