"""Read-only tools the assistant can call. The model never writes SQL: it picks a tool and gives dates.

Every SQL statement is a fixed template; only validated dates are inserted, so the model cannot
change what is queried or write anything. Athena runs the queries on the Gold tables (DATA-06).

Variables:
    FIRST_DAY, LAST_DAY   - dataset coverage (UCI household, timezone unspecified)
    TABLE                 - Gold hourly table, cited as the source of every SQL answer
    MAX_DAYS              - longest period per tool (forecast/anomaly tool: 7 days, as the inference Lambda)
    SPECS                 - tool descriptions and JSON schemas sent to Bedrock
    QUERIES               - SQL template per SQL tool; {db}, {start}, {end}, {top_n} are filled in after validation
    COLUMNS               - result column names per SQL tool, in SELECT order
"""

import json
from datetime import date, datetime, timedelta

from ml.inference.aws import run_query

FIRST_DAY = date(2006, 12, 16)
LAST_DAY = date(2010, 11, 26)
TABLE = "gold_hourly_consumption"
MAX_DAYS = {"daily_consumption": 62, "forecast_and_anomalies": 7}
DEFAULT_MAX_DAYS = 400

_KWH = "global_active_power_kwh"
_WHERE = "WHERE \"timestamp\" >= TIMESTAMP '{start}' AND \"timestamp\" < TIMESTAMP '{end}'"

QUERIES = {
    "consumption_summary": (
        f"SELECT COUNT(*) AS hours, COUNT_IF(complete) AS complete_hours, "
        f"ROUND(SUM(CASE WHEN complete THEN {_KWH} END), 3) AS total_kwh, "
        f"ROUND(AVG(CASE WHEN complete THEN {_KWH} END), 3) AS avg_kwh_per_hour, "
        f"ROUND(MAX(CASE WHEN complete THEN {_KWH} END), 3) AS max_hour_kwh "
        f"FROM {{db}}.{TABLE} {_WHERE}"
    ),
    "daily_consumption": (
        f"SELECT CAST(date_trunc('day', \"timestamp\") AS date) AS day, COUNT_IF(complete) AS complete_hours, "
        f"ROUND(SUM(CASE WHEN complete THEN {_KWH} END), 3) AS kwh "
        f"FROM {{db}}.{TABLE} {_WHERE} GROUP BY 1 ORDER BY 1"
    ),
    "peak_hours": (
        f"SELECT \"timestamp\", ROUND({_KWH}, 3) AS kwh FROM {{db}}.{TABLE} {_WHERE} "
        f"AND complete ORDER BY {_KWH} DESC, \"timestamp\" LIMIT {{top_n}}"
    ),
    "weekday_vs_weekend": (
        f"SELECT CASE WHEN day_of_week(\"timestamp\") >= 6 THEN 'weekend' ELSE 'weekday' END AS day_type, "
        f"COUNT_IF(complete) AS complete_hours, ROUND(AVG(CASE WHEN complete THEN {_KWH} END), 3) AS avg_kwh_per_hour "
        f"FROM {{db}}.{TABLE} {_WHERE} GROUP BY 1 ORDER BY 1"
    ),
    "hourly_profile": (
        f"SELECT hour(\"timestamp\") AS hour_of_day, COUNT_IF(complete) AS complete_hours, "
        f"ROUND(AVG(CASE WHEN complete THEN {_KWH} END), 3) AS avg_kwh "
        f"FROM {{db}}.{TABLE} {_WHERE} GROUP BY 1 ORDER BY 1"
    ),
    "submetering_breakdown": (
        f"SELECT ROUND(SUM({_KWH}), 3) AS total_kwh, ROUND(SUM(sub_metering_1_kwh), 3) AS kitchen_kwh, "
        f"ROUND(SUM(sub_metering_2_kwh), 3) AS laundry_kwh, ROUND(SUM(sub_metering_3_kwh), 3) AS water_heater_ac_kwh, "
        f"ROUND(SUM({_KWH}) - SUM(sub_metering_1_kwh) - SUM(sub_metering_2_kwh) - SUM(sub_metering_3_kwh), 3) "
        f"AS other_kwh, COUNT(*) AS complete_hours FROM {{db}}.{TABLE} {_WHERE} AND complete"
    ),
}

COLUMNS = {
    "consumption_summary": ["hours", "complete_hours", "total_kwh", "avg_kwh_per_hour", "max_hour_kwh"],
    "daily_consumption": ["day", "complete_hours", "kwh"],
    "peak_hours": ["timestamp", "kwh"],
    "weekday_vs_weekend": ["day_type", "complete_hours", "avg_kwh_per_hour"],
    "hourly_profile": ["hour_of_day", "complete_hours", "avg_kwh"],
    "submetering_breakdown": ["total_kwh", "kitchen_kwh", "laundry_kwh", "water_heater_ac_kwh", "other_kwh", "complete_hours"],
}

_PERIOD = {
    "start": {"type": "string", "description": "First day, inclusive, YYYY-MM-DD"},
    "end": {"type": "string", "description": "Day after the last day, exclusive, YYYY-MM-DD"},
}


def _spec(name, description, extra=None):
    properties = {**_PERIOD, **(extra or {})}
    return {"toolSpec": {"name": name, "description": description, "inputSchema": {"json": {
        "type": "object", "properties": properties, "required": ["start", "end"]}}}}


SPECS = [
    _spec("consumption_summary", "Total and average consumption (kWh) and data completeness for a period."),
    _spec("daily_consumption", "Consumption per day (kWh) for a period of at most 62 days."),
    _spec("peak_hours", "The highest-consumption hours in a period.",
          {"top_n": {"type": "integer", "description": "How many hours, 1-10 (default 3)"}}),
    _spec("weekday_vs_weekend", "Average consumption per hour on weekdays versus weekends for a period."),
    _spec("hourly_profile", "Average consumption for each hour of the day (0-23) over a period."),
    _spec("submetering_breakdown",
          "Consumption split into kitchen, laundry, water heater and air conditioning, and everything else."),
    _spec("forecast_and_anomalies",
          "Day-ahead forecast and detected anomalies (log-MAD and Random Cut Forest) for at most 7 days."),
]


def _day(value):
    """A date from "YYYY-MM-DD" or a midnight "YYYY-MM-DDT00:00:00"; anything else raises ValueError."""
    text = str(value)
    if len(text) == 10:
        return date.fromisoformat(text)
    moment = datetime.fromisoformat(text)
    if moment.tzinfo or moment != datetime.combine(moment.date(), datetime.min.time()):
        raise ValueError(text)
    return moment.date()


def parse_period(name, args):
    """Validated (start, end) datetimes for a tool call; raises ValueError with a message for the model."""
    try:
        start, end = _day(args["start"]), _day(args["end"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("start and end must be dates in YYYY-MM-DD format") from None
    if not start < end:
        raise ValueError("end must be after start (end is exclusive)")
    if start < FIRST_DAY or end > LAST_DAY + timedelta(days=1):
        raise ValueError(f"data covers {FIRST_DAY} to {LAST_DAY}; choose dates inside that range")
    limit = MAX_DAYS.get(name, DEFAULT_MAX_DAYS)
    if (end - start).days > limit:
        raise ValueError(f"{name} accepts at most {limit} days")
    return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time())


def build_sql(name, args, database):
    """Final SQL for a SQL tool after validation."""
    start, end = parse_period(name, args)
    top_n = int(args.get("top_n", 3)) if name == "peak_hours" else 0
    if name == "peak_hours" and not 1 <= top_n <= 10:
        raise ValueError("top_n must be between 1 and 10")
    return QUERIES[name].format(db=database, start=f"{start:%Y-%m-%d %H:%M:%S}", end=f"{end:%Y-%m-%d %H:%M:%S}", top_n=top_n)


def run_tool(name, args, clients, env):
    """Tool result as a JSON-friendly dict: {"source", "columns", "rows"} or the inference Lambda response."""
    if name == "forecast_and_anomalies":
        start, end = parse_period(name, args)
        payload = json.dumps({"start": start.isoformat(), "end": end.isoformat()})
        response = clients["lambda"].invoke(FunctionName=env["INFERENCE_FUNCTION"], Payload=payload)
        result = json.loads(response["Payload"].read())
        if "error" in result or "errorMessage" in result:
            raise ValueError(result.get("error") or result.get("errorMessage"))
        # Keep what the model needs: hourly forecast and the anomaly list.
        return {
            "source": "ml-inference",
            "forecast_kwh": [[p["timestamp"], round(p["predicted_kwh"], 3)] for p in result["forecast"]["predictions"]],
            "anomalies": result["anomalies"]["anomalies"],
        }
    if name not in QUERIES:
        raise ValueError(f"unknown tool {name}")
    sql = build_sql(name, args, env["ATHENA_DATABASE"])
    rows = run_query(clients.get("athena"), sql, env["ATHENA_WORKGROUP"])
    return {"source": TABLE, "columns": COLUMNS[name], "rows": rows}
