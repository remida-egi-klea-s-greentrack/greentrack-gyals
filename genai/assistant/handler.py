"""Assistant Lambda (Challenge 4): chat answers and the weekly report.

Events:
    {"message": "...", "session_id": "..."}      -> {"answer", "citations", "tools_used"} (contracts/chat.json)
    {"report": "weekly", "week_start": "YYYY-MM-DD"} -> {"report", "citations", "tools_used"}
    An API Gateway proxy event (JSON "body") gets a proxy response: statusCode 200, or 400 with {"error"}.

Variables (Lambda environment):
    MODEL_ID                        - Bedrock model or inference profile id (Claude Haiku, eu. profile)
    GUARDRAIL_ID, GUARDRAIL_VERSION - Bedrock guardrail applied to every model call
    ATHENA_DATABASE, ATHENA_WORKGROUP - Gold database and workgroup
    INFERENCE_FUNCTION              - forecast/anomaly Lambda used by the forecast_and_anomalies tool
    KNOWLEDGE_BASE_ID               - Bedrock Knowledge Base used by the energy_saving_advice tool
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
            result = _run(json.loads(event["body"] or "{}"), bedrock, clients, env)
        except json.JSONDecodeError:
            result = {"error": "Body must be JSON"}
        return {"statusCode": 400 if "error" in result else 200,
                "headers": {"Content-Type": "application/json"}, "body": json.dumps(result)}
    return _run(event, bedrock, clients, env)


def _run(event, bedrock, clients, env):
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
        clients={"athena": boto3.client("athena"), "lambda": boto3.client("lambda", config=Config(read_timeout=150)),
                 "bedrock_agent": boto3.client("bedrock-agent-runtime", config=retries)},
        env=os.environ,
    )
