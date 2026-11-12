"""Conversation loop with Claude on Bedrock (Converse API, tool use, Guardrails) and the weekly report.

Variables:
    SYSTEM_PROMPT  - rules: answer only from tool results, refuse out-of-scope and write requests
    MAX_TURNS      - model calls per question (each tool round is one call)
    REFUSAL        - answer when the guardrail blocks a request or the loop runs out of turns
    bedrock        - bedrock-runtime client; clients - {"athena", "lambda"}; env - Lambda environment
"""

import json
from datetime import date, timedelta

from genai.assistant import tools

MAX_TURNS = 6
REFUSAL = "I can only answer questions about this household's electricity consumption data."

SYSTEM_PROMPT = f"""You are GreenTrack's energy assistant for ONE household's historical electricity data.
Data: hourly consumption in kWh from {tools.FIRST_DAY} to {tools.LAST_DAY} (timezone unspecified).
Treat {tools.LAST_DAY} as "today": resolve "last week", "yesterday", "last Tuesday" relative to it, and state the exact dates you used.

Rules:
- Every number you give must come from a tool result in this conversation. Never estimate or invent values.
- Use end dates as exclusive (a single day D is start=D, end=D+1).
- If some hours are incomplete (complete_hours lower than hours), say so briefly.
- To explain why usage was high, compare with a typical period (hourly_profile, weekday_vs_weekend) and use submetering_breakdown.
- Anomaly scores are percentiles, not probabilities.
- The data is read-only. Refuse any request to change, delete, add or upload data, and do not run tools for it.
- Refuse questions unrelated to this household's electricity use or general energy saving, without running tools.
- Answer in 2-5 short sentences, plain text, with units.
"""


def _text(message):
    return " ".join(block["text"] for block in message["content"] if "text" in block).strip()


def converse(bedrock, env, messages, use_tools=True):
    kwargs = {
        "modelId": env["MODEL_ID"],
        "system": [{"text": SYSTEM_PROMPT}],
        "messages": messages,
        "inferenceConfig": {"maxTokens": 800, "temperature": 0},
    }
    if use_tools:
        kwargs["toolConfig"] = {"tools": tools.SPECS}
    if env.get("GUARDRAIL_ID"):
        kwargs["guardrailConfig"] = {"guardrailIdentifier": env["GUARDRAIL_ID"], "guardrailVersion": env["GUARDRAIL_VERSION"]}
    return bedrock.converse(**kwargs)


def answer(question, bedrock, clients, env):
    """Chat contract response: {"answer", "citations", "tools_used"}."""
    messages = [{"role": "user", "content": [{"text": question}]}]
    citations, used = set(), []

    for _ in range(MAX_TURNS):
        response = converse(bedrock, env, messages)
        message = response["output"]["message"]
        messages.append(message)

        if response["stopReason"] == "guardrail_intervened":
            return {"answer": _text(message) or REFUSAL, "citations": [], "tools_used": []}
        if response["stopReason"] != "tool_use":
            return {"answer": _text(message), "citations": sorted(citations), "tools_used": used}

        results = []
        for block in message["content"]:
            if "toolUse" not in block:
                continue
            call = block["toolUse"]
            used.append(call["name"])
            try:
                result = tools.run_tool(call["name"], call["input"], clients, env)
                citations.add(result["source"])
                content, status = [{"json": result}], "success"
            except (ValueError, RuntimeError, TimeoutError) as error:
                content, status = [{"text": f"Tool error: {error}"}], "error"
            results.append({"toolResult": {"toolUseId": call["toolUseId"], "content": content, "status": status}})
        messages.append({"role": "user", "content": results})

    return {"answer": REFUSAL, "citations": sorted(citations), "tools_used": used}


def weekly_report(week_start, bedrock, clients, env):
    """Narrative summary of one week (7 days from week_start) from fixed tool calls; no free-form tool use."""
    week = {"start": week_start, "end": _plus_days(week_start, 7)}
    previous = {"start": _plus_days(week_start, -7), "end": week_start}
    tools.parse_period("forecast_and_anomalies", week)  # validates the week before any call
    facts = {
        "week": tools.run_tool("consumption_summary", week, clients, env),
        "previous_week": tools.run_tool("consumption_summary", previous, clients, env),
        "daily": tools.run_tool("daily_consumption", week, clients, env),
        "peaks": tools.run_tool("peak_hours", {**week, "top_n": 3}, clients, env),
        "submetering": tools.run_tool("submetering_breakdown", week, clients, env),
        "forecast_and_anomalies": tools.run_tool("forecast_and_anomalies", week, clients, env),
    }
    prompt = (
        f"Write a weekly energy report for {week['start']} to {week['end']} (end exclusive) in 5-8 short sentences: "
        "total and change versus the previous week, busiest day and peak hours, where the energy went (submetering), "
        "detected anomalies (say which detector), and how close the forecast was to the actual daily totals if you can tell. "
        "Use only these facts:\n" + json.dumps(facts, default=str)
    )
    response = converse(bedrock, env, [{"role": "user", "content": [{"text": prompt}]}], use_tools=False)
    if response["stopReason"] == "guardrail_intervened":
        return {"report": REFUSAL, "citations": [], "tools_used": []}
    return {
        "report": _text(response["output"]["message"]),
        "citations": sorted({f["source"] for f in facts.values()}),
        "tools_used": list(facts),
    }


def _plus_days(day, days):
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()
