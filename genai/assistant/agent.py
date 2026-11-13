"""Conversation loop with Claude on Bedrock (Converse API, tool use, Guardrails) and the weekly report.

Variables:
    SYSTEM_PROMPT  - rules: answer only from tool results, refuse out-of-scope and write requests
    MAX_TURNS      - model calls per question (each tool round is one call)
    REFUSAL        - answer when the guardrail blocks a request or the loop runs out of turns
    bedrock        - bedrock-runtime client; clients - {"athena", "lambda", "bedrock_agent"}; env - Lambda environment
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
- The dataset does not specify a time zone: never name one (ignore any "UTC" suffix on timestamps).
- For advice on saving energy, call energy_saving_advice and give only advice found in its passages; say which
  guidance documents you used. Where it helps, check the household's data first (e.g. submetering_breakdown).
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


def user_turn(text, env):
    """First user message. With a guardrail, only this text is assessed (guardContent): not the system
    prompt, the tool results or our own facts, which are trusted and would trigger false blocks."""
    block = {"guardContent": {"text": {"text": text}}} if env.get("GUARDRAIL_ID") else {"text": text}
    return {"role": "user", "content": [block]}


def answer(question, bedrock, clients, env):
    """Chat contract response: {"answer", "citations", "tools_used"}."""
    messages = [user_turn(question, env)]
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
                citations.update(result.get("documents") or [result["source"]])
                content, status = [{"json": result}], "success"
            except (ValueError, RuntimeError, TimeoutError) as error:
                content, status = [{"text": f"Tool error: {error}"}], "error"
            results.append({"toolResult": {"toolUseId": call["toolUseId"], "content": content, "status": status}})
        messages.append({"role": "user", "content": results})

    return {"answer": REFUSAL, "citations": sorted(citations), "tools_used": used}


def forecast_vs_actual(daily, forecast):
    """Daily forecast and actual totals (kWh) for complete days with 24 forecast hours, plus their mean absolute error.

    daily - daily_consumption tool result (rows: day, complete_hours, kwh); forecast - forecast_and_anomalies result.
    """
    predicted = {}
    for timestamp, kwh in forecast["forecast_kwh"]:
        predicted.setdefault(str(timestamp)[:10], []).append(kwh)
    days = []
    for row in daily["rows"]:
        if len(row) != 3:
            continue
        day, complete_hours, kwh = row
        hours = predicted.get(str(day)[:10], [])
        if complete_hours is None or kwh is None or int(complete_hours) != 24 or len(hours) != 24:
            continue
        f, a = round(sum(hours), 3), round(float(kwh), 3)
        days.append({"day": str(day)[:10], "forecast_kwh": f, "actual_kwh": a, "error_kwh": round(f - a, 3)})
    mae = round(sum(abs(d["error_kwh"]) for d in days) / len(days), 3) if days else None
    return {"days": days, "mean_abs_daily_error_kwh": mae}


SUBMETER_PARTS = {"kitchen_kwh": "kitchen", "laundry_kwh": "laundry", "water_heater_ac_kwh": "water heater and AC",
                  "other_kwh": "other (no sub-meter)"}


def submetering_shares(submetering):
    """Parts of the week's consumption, largest first: [{"part", "kwh", "percent"}] (empty if no data).

    submetering - submetering_breakdown tool result (columns and one row of kWh values as strings).
    """
    if not submetering["rows"] or len(submetering["rows"][0]) != len(submetering["columns"]):
        return []
    row = dict(zip(submetering["columns"], submetering["rows"][0]))
    parts = {label: float(row[col]) for col, label in SUBMETER_PARTS.items() if row.get(col) is not None}
    total = sum(parts.values())
    if total <= 0:
        return []
    return [{"part": label, "kwh": round(kwh, 1), "percent": round(100 * kwh / total)}
            for label, kwh in sorted(parts.items(), key=lambda kv: -kv[1])]


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
    # Only the short request is guarded: the rules below are our own text, and their imperative wording
    # trips the guardrail's prompt-attack filter (seen live on 12 Nov 2026).
    request = f"Write a weekly energy report for {week['start']} to {_plus_days(week_start, 6)}."  # both days included
    rules = (
        "Report rules: 5-8 short sentences covering "
        "total and change versus the previous week, busiest day and peak hours, where the energy went (submetering), "
        "detected anomalies (say which detector), and how close the forecast was, using forecast_vs_actual (daily totals "
        "and mean absolute daily error; if it has no days, say the comparison is not available). "
        "For where the energy went, use submetering_shares: it is sorted largest first, so the first part is the "
        "largest. The dataset does not specify a time zone, so no time zone is named. Use only the facts given."
    )
    message = user_turn(request, env)
    comparison = forecast_vs_actual(facts["daily"], facts["forecast_and_anomalies"])
    message["content"].insert(0, {"text": "Facts (JSON): " + json.dumps({**facts, "forecast_vs_actual": comparison,
                                                                         "submetering_shares": submetering_shares(facts["submetering"])},
                                                                         default=str)})
    message["content"].append({"text": rules})
    response = converse(bedrock, env, [message], use_tools=False)
    if response["stopReason"] == "guardrail_intervened":
        return {"report": REFUSAL, "citations": [], "tools_used": []}
    return {
        "report": _text(response["output"]["message"]),
        "citations": sorted({f["source"] for f in facts.values()}),
        "tools_used": list(facts),
    }


def _plus_days(day, days):
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()
