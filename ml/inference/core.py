"""Pure logic of the inference Lambda: window checks, features, shingles, scores, response.

Standard library only, so the Lambda package needs no numpy/pandas.

Variables:
    MAX_DAYS          - longest window one call may request
    HISTORY           - history needed before the window (lag_168h of the first 00:00 target)
    SHINGLE_HOURS     - RCF window length (same as the trained model's feature_dim)
    SEVERITY_LEVELS   - percentile cut-offs shared by both detectors
    hours             - dict {datetime hour start: kWh or None}; None = missing or incomplete hour
    params            - dict from inference/params.json: log_mad.medians / mads (168 hour-of-week slots,
                        Monday 00:00 = 0), log_mad.reference (sorted 2009 |z|), rcf.reference (sorted 2009 scores)
"""

from bisect import bisect_right
from datetime import datetime, timedelta
from math import log

MAX_DAYS = 7
HISTORY = timedelta(hours=168)
SHINGLE_HOURS = 24
SEVERITY_LEVELS = [(0.999, "high"), (0.995, "medium"), (0.99, "low")]
MAD_SCALE = 1.4826


def parse_window(event, first_hour, last_hour):
    """Validated (start, end) datetimes from {"start", "end"}; raises ValueError with a clear message."""
    try:
        start = datetime.fromisoformat(event["start"])
        end = datetime.fromisoformat(event["end"])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Expected {"start": "YYYY-MM-DDT00:00:00", "end": "YYYY-MM-DDT00:00:00"}') from None
    if start.tzinfo or end.tzinfo:
        raise ValueError("Timestamps must be timezone-naive (dataset timezone is unspecified)")
    if any(t != t.replace(hour=0, minute=0, second=0, microsecond=0) for t in (start, end)):
        raise ValueError("start and end must be midnights (whole days)")
    if not start < end <= start + timedelta(days=MAX_DAYS):
        raise ValueError(f"end must be after start and at most {MAX_DAYS} days later")
    if start - HISTORY < first_hour:
        raise ValueError(f"start needs 7 days of history; earliest allowed start is {first_hour + HISTORY:%Y-%m-%d} or later midnight")
    if end > last_hour + timedelta(hours=1):
        raise ValueError(f"end is after the last available hour ({last_hour:%Y-%m-%d %H:%M})")
    return start, end


def hour_range(start, end):
    """Hour starts in [start, end)."""
    count = int((end - start) / timedelta(hours=1))
    return [start + timedelta(hours=i) for i in range(count)]


def forecast_rows(hours, day):
    """24 feature rows for target day `day`, using only hours up to day - 1 h (same as ml/forecasting/features.py).

    Row order follows FEATURE_COLUMNS: hour, day_of_week, month, lag_24h_kwh, lag_168h_kwh, mean_last_24h_kwh.
    """
    last_24 = [hours.get(day - timedelta(hours=h)) for h in range(1, 25)]
    mean_last_24 = sum(last_24) / 24 if None not in last_24 else None
    rows = []
    for target in hour_range(day, day + timedelta(days=1)):
        rows.append([
            target.hour,
            target.weekday(),
            target.month,
            hours.get(target - timedelta(hours=24)),
            hours.get(target - timedelta(hours=168)),
            mean_last_24,
        ])
    return rows


def shingles(hours, targets):
    """{target: 24 values ending at target} for targets whose whole window is observed."""
    out = {}
    for target in targets:
        values = [hours.get(target - timedelta(hours=h)) for h in range(SHINGLE_HOURS - 1, -1, -1)]
        if None not in values:
            out[target] = values
    return out


def percentile(sorted_reference, value):
    """Share of reference scores <= value (0..1); same rule as the Python detectors."""
    return bisect_right(sorted_reference, value) / len(sorted_reference)


def severity(score):
    """low / medium / high, or None below the lowest cut-off."""
    for cutoff, level in SEVERITY_LEVELS:
        if score >= cutoff:
            return level
    return None


def log_mad_scores(hours, targets, params):
    """{target: percentile} for observed targets, from slot medians/MADs fitted on the FIT period."""
    medians, mads = params["log_mad"]["medians"], params["log_mad"]["mads"]
    reference = params["log_mad"]["reference"]
    out = {}
    for target in targets:
        value = hours.get(target)
        if value is None or value <= 0:  # log needs a positive value; Gold complete hours are positive
            continue
        slot = target.weekday() * 24 + target.hour
        z = (log(value) - medians[slot]) / (MAD_SCALE * mads[slot])
        out[target] = percentile(reference, abs(z))
    return out


def build_response(window, hours, predictions, rcf_scores, mad_scores, generated_at):
    """Response with contract-shaped forecast and anomalies plus every hour's scores.

    predictions: {target: kWh}; rcf_scores / mad_scores: {target: percentile}.
    """
    start, end = window
    targets = hour_range(start, end)
    detectors = {"log_mad": mad_scores, "rcf_raw_24": rcf_scores}

    forecast = [{
        "timestamp": t.isoformat(),
        "forecast_origin": t.replace(hour=0).isoformat(),
        # Consumption cannot be negative (same clipping as ML-03).
        "predicted_kwh": max(0.0, predictions[t]),
        "lower_bound": None,
        "upper_bound": None,
    } for t in targets if t in predictions]

    anomalies = [{
        "timestamp": t.isoformat(),
        "consumption_kwh": hours[t],
        "anomaly_score": scores[t],
        "severity": severity(scores[t]),
        "detector": name,
    } for t in targets for name, scores in detectors.items() if t in scores and severity(scores[t])]

    scores = [{
        "timestamp": t.isoformat(),
        "consumption_kwh": hours.get(t),
        **{name: values.get(t) for name, values in detectors.items()},
    } for t in targets]

    stamp = generated_at.isoformat()
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "forecast": {"generated_at": stamp, "unit": "kWh", "predictions": forecast},
        "anomalies": {"generated_at": stamp, "anomalies": anomalies},
        "scores": scores,
    }
