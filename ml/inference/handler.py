"""Lambda entry point: forecast and anomaly scores for a time window (Challenge 3 "done when").

Invoke with {"start": "2010-03-01T00:00:00", "end": "2010-03-04T00:00:00"}.

Variables (Lambda environment):
    XGBOOST_ENDPOINT, RCF_ENDPOINT  - SageMaker endpoint names
    ATHENA_DATABASE, ATHENA_WORKGROUP - Gold database and workgroup (results location is set by the workgroup)
    PARAMS_BUCKET, PARAMS_KEY       - S3 location of params.json
    FIRST_HOUR, LAST_HOUR           - first/last Gold hour (defaults: the UCI dataset range)
    _params                         - params.json cached across warm invocations
"""

import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

from ml.inference import aws, core

_params = None


def run(event, athena, runtime, s3, env, now):
    """Whole request with injected clients, so tests run without AWS."""
    global _params
    try:
        window = core.parse_window(
            event,
            datetime.fromisoformat(env.get("FIRST_HOUR", "2006-12-16T17:00:00")),
            datetime.fromisoformat(env.get("LAST_HOUR", "2010-11-26T21:00:00")),
        )
    except ValueError as error:
        return {"error": str(error)}

    if _params is None:
        _params = aws.load_params(s3, env["PARAMS_BUCKET"], env["PARAMS_KEY"])

    start, end = window
    hours = aws.query_hours(athena, env["ATHENA_DATABASE"], env["ATHENA_WORKGROUP"], start - core.HISTORY, end)
    targets = core.hour_range(start, end)

    days = [start + timedelta(days=d) for d in range((end - start).days)]
    rows = [row for day in days for row in core.forecast_rows(hours, day)]
    predictions = dict(zip(targets, aws.predict_xgboost(runtime, env["XGBOOST_ENDPOINT"], rows)))

    windows = core.shingles(hours, targets)
    raw = aws.score_rcf(runtime, env["RCF_ENDPOINT"], list(windows.values())) if windows else []
    reference = _params["rcf"]["reference"]
    rcf_scores = {t: core.percentile(reference, s) for t, s in zip(windows, raw)}

    mad_scores = core.log_mad_scores(hours, targets, _params)
    return core.build_response(window, hours, predictions, rcf_scores, mad_scores, now)


def lambda_handler(event, context):
    retries = Config(retries={"mode": "standard", "max_attempts": 5}, read_timeout=70)
    return run(
        event,
        athena=boto3.client("athena"),
        runtime=boto3.client("sagemaker-runtime", config=retries),
        s3=boto3.client("s3"),
        env=os.environ,
        now=datetime.now(timezone.utc),
    )
