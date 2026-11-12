"""AWS calls of the inference Lambda: Athena (Gold hours), SageMaker endpoints, params.json.

Variables:
    QUERY            - read-only SELECT on the Gold hourly table; only columns we need, bounded by time
    POLL_SECONDS     - wait between Athena status checks
    BATCH_SIZE       - records per InvokeEndpoint call (far below the 4 MB serverless payload limit)
    athena, runtime, s3 - boto3 clients (stubbed in tests)
"""

import json
import time
from datetime import datetime

QUERY = (
    'SELECT "timestamp", global_active_power_kwh, complete '
    "FROM {database}.gold_hourly_consumption "
    "WHERE \"timestamp\" >= TIMESTAMP '{start:%Y-%m-%d %H:%M:%S}' "
    "AND \"timestamp\" < TIMESTAMP '{end:%Y-%m-%d %H:%M:%S}' "
    'ORDER BY "timestamp"'
)
POLL_SECONDS = 0.5
BATCH_SIZE = 500


def run_query(athena, sql, workgroup, timeout_seconds=60, sleep=time.sleep):
    """Rows of a read-only Athena query as lists of strings (None for NULL), header row removed.

    The query is cancelled if it does not finish within timeout_seconds.
    """
    query_id = athena.start_query_execution(QueryString=sql, WorkGroup=workgroup)["QueryExecutionId"]

    waited = 0.0
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        if status["State"] == "SUCCEEDED":
            break
        if status["State"] in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Athena query {status['State']}: {status.get('StateChangeReason', '')}")
        if waited >= timeout_seconds:
            athena.stop_query_execution(QueryExecutionId=query_id)
            raise TimeoutError(f"Athena query did not finish in {timeout_seconds} s (cancelled)")
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS

    rows, token, first_page = [], None, True
    while True:
        page = athena.get_query_results(QueryExecutionId=query_id, **({"NextToken": token} if token else {}))
        page_rows = page["ResultSet"]["Rows"]
        for row in page_rows[1:] if first_page else page_rows:  # first row of the first page is the header
            rows.append([cell.get("VarCharValue") for cell in row["Data"]])
        first_page = False
        token = page.get("NextToken")
        if not token:
            return rows


def query_hours(athena, database, workgroup, start, end, timeout_seconds=60, sleep=time.sleep):
    """{hour: kWh or None} for [start, end); incomplete hours map to None.

    start/end are validated datetimes, so formatting them into the SQL cannot inject anything.
    """
    sql = QUERY.format(database=database, start=start, end=end)
    hours = {}
    for stamp, kwh, complete in run_query(athena, sql, workgroup, timeout_seconds, sleep):
        hours[datetime.fromisoformat(stamp[:19])] = float(kwh) if complete == "true" and kwh is not None else None
    return hours


def _csv(rows):
    """CSV body; None becomes an empty field, which the built-in containers read as missing."""
    return "\n".join(",".join("" if v is None else repr(float(v)) for v in row) for row in rows)


def predict_xgboost(runtime, endpoint, rows):
    """Predicted kWh per feature row (built-in XGBoost, text/csv in and out)."""
    out = []
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        body = runtime.invoke_endpoint(
            EndpointName=endpoint, ContentType="text/csv", Accept="text/csv", Body=_csv(chunk),
        )["Body"].read().decode()
        # The container separates predictions with commas or newlines depending on version.
        values = [float(v) for v in body.replace("\n", ",").split(",") if v.strip()]
        if len(values) != len(chunk):
            raise ValueError(f"Expected {len(chunk)} predictions, got {len(values)}")
        out.extend(values)
    return out


def score_rcf(runtime, endpoint, records):
    """Raw RCF score per 24-value record; same request format as ml/sagemaker/rcf_compare.py."""
    out = []
    for i in range(0, len(records), BATCH_SIZE):
        chunk = records[i:i + BATCH_SIZE]
        body = "\n".join(",".join(f"{v:.6f}" for v in row) for row in chunk)
        response = runtime.invoke_endpoint(
            EndpointName=endpoint, ContentType="text/csv", Accept="application/json", Body=body,
        )
        scores = [item["score"] for item in json.loads(response["Body"].read())["scores"]]
        if len(scores) != len(chunk):
            raise ValueError(f"Expected {len(chunk)} scores, got {len(scores)}")
        out.extend(scores)
    return out


def load_params(s3, bucket, key):
    """Detector parameters and calibration references written by the calibrate command."""
    return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
