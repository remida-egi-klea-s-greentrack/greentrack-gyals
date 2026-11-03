# GreenTrack — Forecasting Evaluation

## Objective

Evaluate 24-hour electricity consumption forecasts against
daily and weekly seasonal naive baselines.

## Chronological data split

- Training: 2006-12-16 through 2009-12-31
- Validation: 2010-01-01 through 2010-05-31
- Test: 2010-06-01 through 2010-11-25

The test period is reserved for final model comparison.
Do not use its forecasting errors for model selection or tuning.

## Forecasting protocol

- Forecast horizon: 24 hours
- Forecast frequency: once per day
- Daily baseline: value 24 hours earlier
- Weekly baseline: value 168 hours earlier
- Each forecast predicts 00:00–23:00 of the target day.
- Hourly timestamps represent the start of their respective hours.
- The forecast is issued at midnight, after the previous
  day's 23:00–23:59 observation is complete.

Both baselines are evaluated on identical forecast days.

A day is excluded if any target observation, daily historical
reference, or weekly historical reference is missing.

## Metrics

- RMSE (kWh)
- MAE (kWh)
- MAPE (%)

Overall metrics are pooled across hourly predictions.
Per-day metrics are also retained.

MAPE requires strictly positive actual consumption.

## Validation results

Period: January–May 2010

- Candidate days: 151
- Eligible days: 121
- Excluded days: 30
- Forecast hours: 2,904

| Baseline | RMSE (kWh) | MAE (kWh) | MAPE (%) |
| --- | ---: | ---: | ---: |
| Daily | 0.8818 | 0.6185 | 73.31 |
| Weekly | 0.8721 | 0.6108 | 72.26 |

These are validation results, not final test-set results.

## Reproduce validation

From the repository root, with the Python environment active:

python -m ml.forecasting.run_validation \
  --input /path/to/hourly_consumption.parquet \
  --output /path/to/report-directory

The input Parquet file must contain:
- timestamp
- global_active_power_kwh
- complete

Incomplete hours must have null consumption values.

The script generates hourly predictions, per-day metrics,
overall metrics, exclusions, and a source-checksum manifest.

## Reproducibility limitation

The current hourly reference dataset was generated locally.
The raw-to-hourly transformation must be made reproducible
through the data engineering pipeline before end-to-end
reproducibility can be claimed.

## ML-04 — Electricity consumption anomaly detection

### Approach

The local baseline uses global hour-of-week log-MAD:

1. Transform positive hourly consumption to log(kWh).
2. Learn a median and Median Absolute Deviation (MAD) for each of the 168 hours of the week.
3. Calculate signed robust z-scores using `1.4826 * MAD`.
4. Convert absolute deviations to percentiles of training deviations.
5. Assign severity using training-calibrated thresholds.

Fitting requires at least 30 valid observations per hour-of-week group and positive MAD in every group.

This is an interpretable local benchmark for the planned SageMaker Random Cut Forest implementation, not a production-validated anomaly alarm.

### Data split and leakage prevention

- Training: available observations through 2009-12-31 23:00.
- Validation: 2010-01-01 00:00 through 2010-05-31 23:00.
- Reserved test: 2010-06-01 00:00 through 2010-11-25 23:00.

The split is consistent with the forecasting evaluation. The detector is fitted and calibrated only on training observations. Validation data does not update the fitted statistics or thresholds. The reserved test period has not been evaluated.

Incomplete hourly observations remain unscored.

### Scores and API

`GlobalLogMADDetector.score()` returns every input hour, including unflagged and incomplete observations. The `robust_z` field is retained for diagnostics.

`ml/anomaly/api.py` converts scored observations into the shared `contracts/anomaly.json` format, returning only flagged anomalies.

`anomaly_score` is a training-calibrated empirical percentile in [0, 1], not the probability of a real anomaly.

| Anomaly score | Severity |
| --- | --- |
| score < 0.99 | Normal (not returned as an alert) |
| 0.99 <= score < 0.995 | Low |
| 0.995 <= score < 0.999 | Medium |
| score >= 0.999 | High |

The UI should use `severity` for alert styling and notification policy rather than interpreting raw model-specific scores.

Observation timestamps are currently timezone-naive. Production timestamp semantics must be agreed with Developers A and C.

### Validation results

The reference dataset produced:

| Metric | Result |
| --- | ---: |
| Valid training hours | 26,477 |
| Valid validation hours | 3,529 |
| Training alert rate | Approximately 0.99% |
| Validation alerts | 18 |
| Validation alert rate | 0.51% |
| Low / medium / high | 9 / 9 / 0 |
| Distinct alert episodes | 12 |
| Longest episode | 4 hours |

An episode is a sequence of consecutive flagged hourly observations.

Fourteen of the 18 validation alerts occurred in January or February. All 18 represented consumption above the fitted hour-of-week median; no low-consumption alerts were observed in validation.

The lower validation alert rate may reflect differences in consumption distributions, but does not independently establish drift.

These figures describe alert behavior, not verified anomaly detection accuracy.

### Synthetic-anomaly sensitivity evaluation

Using random seed 42, forty originally unflagged validation hours were selected and modified:

| Controlled injection | Detected |
| --- | --- |
| 20 observations multiplied by 5 | 5/20 (25%) |
| 20 observations multiplied by 0.2 | 0/20 (0%) |

All 40 modifications produced deviations in the expected direction. Scores of unmodified observations remained identical.

The experiment demonstrates limited sensitivity, particularly to consumption decreases. Its results are specific to these injected changes and cannot be interpreted as real-world recall or precision.

The model and alert thresholds were not adjusted to improve these results.

### Reproduce locally

Run from the repository root with ML dependencies installed.

Validation report:

`python -m ml.anomaly.run_validation --input ~/greentrack-local-data/reference/hourly_consumption.parquet --output ~/greentrack-local-data/reports/ml-04-validation`

Synthetic evaluation:

`python -m ml.anomaly.run_synthetic --input ~/greentrack-local-data/reference/hourly_consumption.parquet --output ~/greentrack-local-data/reports/ml-04-synthetic`

Validation outputs: `scores.csv`, `anomalies.csv`, `monthly_summary.csv`, `episodes.csv`, and `manifest.json`.

Synthetic outputs: `injections.csv` and `manifest.json`.

Both manifests record the input dataset SHA-256 checksum. Generated data and reports are stored outside Git.

Automated tests:

`python -m pytest ml/tests/ -q -W error`

### Known limitations and future work

- No verified anomaly ground-truth labels are available.
- Seasonal bias remains: winter usage produces more alerts, and summer absences can produce unusual low-consumption patterns.
- No low-consumption anomalies were flagged in validation or in the tested 0.2x synthetic decreases.
- The detector may miss substantial changes because thresholds are calibrated to the heavy-tailed training distribution.
- Percentile calibration uses in-sample training deviations.
- The validation window does not cover August holiday behavior.
- Repeated alerts may belong to one incident; notification deduplication is separate from scoring.
- The prepared hourly reference dataset still needs integration with the reproducible upstream data pipeline.
- SageMaker Random Cut Forest, AWS deployment, and model comparison remain future work.
