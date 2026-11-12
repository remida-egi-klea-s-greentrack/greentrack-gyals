"""Assistant Lambda (Challenge 4): chat answers and the weekly report.

Events:
    {"message": "...", "session_id": "..."}      -> {"answer", "citations", "tools_used"} (contracts/chat.json)
    {"report": "weekly", "week_start": "YYYY-MM-DD"} -> {"report", "citations", "tools_used"}
    An API Gateway proxy event with the chat request as a JSON "body" is accepted too.

Variables (Lambda environment):
    MODEL_ID                        - Bedrock model or inference profile id (Claude Haiku, eu. profile)
    GUARDRAIL_ID, GUARDRAIL_VERSION - Bedrock guardrail applied to every model call
    ATHENA_DATABASE, ATHENA_WORKGROUP - Gold database and workgroup
    INFERENCE_FUNCTION              - forecast/anomaly Lambda used by the forecast_and_anomalies tool
"""

import json
import os

import boto3
from botocore.config import Config

from genai.assistant import agent

MAX_MESSAGE_CHARS = 1000


def run(event, bedrock, clients, env):
    """Whole request with injected clients, so tests run without AWS."""
    if isinstance(event, dict) and "body" in event:
        try:
            event = json.loads(event["body"] or "{}")
        except json.JSONDecodeError:
            return {"error": "Body must be JSON"}
    if not isinstance(event, dict):
        return {"error": "Request must be a JSON object"}

    try:
        if event.get("report") == "weekly":
            return agent.weekly_report(str(event.get("week_start", "")), bedrock, clients, env)
        message = event.get("message")
        if not isinstance(message, str) or not message.strip():
            return {"error": "Field 'message' is required"}
        if len(message) > MAX_MESSAGE_CHARS:
            return {"error": f"Message longer than {MAX_MESSAGE_CHARS} characters"}
        return agent.answer(message.strip(), bedrock, clients, env)
    except ValueError as error:
        return {"error": str(error)}


def lambda_handler(event, context):
    retries = Config(retries={"mode": "standard", "max_attempts": 4}, read_timeout=100)
    return run(
        event,
        bedrock=boto3.client("bedrock-runtime", config=retries),
        clients={"athena": boto3.client("athena"), "lambda": boto3.client("lambda", config=Config(read_timeout=150))},
        env=os.environ,
    )
