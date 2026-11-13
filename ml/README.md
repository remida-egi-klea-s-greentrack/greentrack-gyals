# GreenTrack — Forecasting Evaluation

## Objective

Evaluate 24-hour electricity consumption forecasts against
daily and weekly seasonal naive baselines.

## Chronological data split

- Training: 2006-12-16 through 2009-12-31
- Validation: 2010-01-01 through 2010-05-31
- Test: 2010-06-01 through 2010-11-25

The test period is used only for the final comparison of the frozen model
(see "Held-out test result"). Its errors were never used for model selection or tuning.

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

## ML-03 — XGBoost forecasting

### Approach

A single XGBoost regressor predicts each of the next 24 hours
independently, using six features:

- hour
- day_of_week
- month
- lag_24h_kwh
- lag_168h_kwh
- mean_last_24h_kwh

Historical features use only observations available at the forecast
origin. Calendar features describe the target hour.

The previous 24-hour mean requires 24 valid observations;
otherwise, it is NaN. Missing historical features are retained
because XGBoost supports missing feature values.

### Training

- Training targets: 2006-12-17 through 2009-12-31
- Training observations: 26,471
- Estimators: 200
- Maximum tree depth: 4
- Learning rate: 0.05
- Subsample: 0.9
- Column subsample: 0.9
- Random seed: 42
- Tree method: hist

The model is trained once and is not retrained during validation.

### Validation comparison

Period: January–May 2010

- Eligible forecast days: 121
- Excluded forecast days: 30
- Hourly predictions: 2,904

| Model | RMSE (kWh) | MAE (kWh) | MAPE (%) |
| --- | ---: | ---: | ---: |
| Daily naive | 0.8818 | 0.6185 | 73.31 |
| Weekly naive | 0.8721 | 0.6108 | 72.26 |
| XGBoost | 0.6232 | 0.4675 | 60.73 |

XGBoost achieved a 28.54% lower validation RMSE than
the weekly baseline and outperformed it on 107 of 121 days.

These figures are validation results, not final test performance.

### Reproduce the experiment

From the repository root:

python -m ml.forecasting.run_xgboost_validation \
  --input /path/to/hourly_consumption.parquet \
  --output /path/to/report-directory

The script saves:

- Hourly predictions for all three models
- Per-day and overall error metrics
- Excluded days and their reasons
- The trained XGBoost model (model.ubj)
- An experiment manifest with model parameters and input checksum

### Limitations

- No hyperparameter optimization has been performed.
- The June–November 2010 test period was evaluated once, with the frozen model (see "Held-out test result").
- Validation performance does not guarantee test performance.
- Nonnegative predictions are not enforced by the regressor.
- End-to-end reproducibility depends on the upstream hourly ETL.
- SageMaker deployment is outside ML-03's scope; it is covered in "AWS deployment (Challenge 3)".

## ML-04 — Electricity consumption anomaly detection

### Approach

The local baseline uses global hour-of-week log-MAD:

1. Transform positive hourly consumption to log(kWh).
2. Learn a median and Median Absolute Deviation (MAD) for each of the 168 hours of the week.
3. Calculate signed robust z-scores using `1.4826 * MAD`.
4. Convert absolute deviations to percentiles of training deviations.
5. Assign severity using training-calibrated thresholds.

Fitting requires at least 30 valid observations per hour-of-week group and positive MAD in every group.

This is the primary, interpretable detector, not a production-validated anomaly alarm. SageMaker Random Cut Forest runs next to it as a secondary detector (see "AWS deployment (Challenge 3)").

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
- The RCF threshold has not been evaluated on the held-out period.

## Held-out test result (forecast)

The model registered as `g2-greentrack-forecast/1` (settings frozen after validation) was evaluated
once on 2010-06-01 through 2010-11-25. Nothing was tuned after this run.

| Model | RMSE (kWh) | MAPE (%) | WAPE (%) |
| --- | ---: | ---: | ---: |
| Daily naive | 0.7184 | 62.42 | 51.33 |
| Weekly naive | 0.7730 | 76.82 | 57.78 |
| XGBoost | 0.5653 | 62.09 | 44.19 |

XGBoost beats both baselines on all three metrics. Its MAPE margin over the daily baseline is small
(0.33 points) because MAPE is inflated by low-consumption hours; WAPE (total absolute error divided by
total consumption) shows the difference more fairly.

## AWS deployment (Challenge 3)

All resources are Terraform (`infra/modules/ml`, applied from `infra/ml`) in `eu-central-1` with the
`g2-greentrack` prefix.

### Training pipeline and Model Registry

`g2-greentrack-forecast-pipeline` (`infra/modules/ml/pipeline.tf`, step code `ml/pipeline/steps.py`):

1. **Prepare** — reads the Gold hourly table through Athena and builds the same features as ML-03.
2. **Train** — built-in SageMaker XGBoost with the frozen ML-03 settings, on spot instances.
3. **Evaluate** — validation window (Jan–May 2010) against the daily and weekly seasonal baselines.
4. **Register** — only if XGBoost beats the best baseline, into the Model Package Group
   `g2-greentrack-forecast` with status `PendingManualApproval`; a person approves the package.

Validation in the pipeline: RMSE 0.6253 vs 0.8721 (weekly) and 0.8818 (daily), MAE 0.4703 vs 0.6108.
The small difference from the local ML-03 figures comes from the built-in algorithm container.

The GitHub Actions workflow **ML Pipeline** (`.github/workflows/ml-pipeline.yml`, manual trigger on
`main`) starts a run and waits for it. It signs in to AWS with OIDC (repository secret
`ML_PIPELINE_ROLE_ARN`); no access keys are stored.

### Random Cut Forest (secondary anomaly detector)

- Built-in SageMaker RCF on raw hourly kWh, 24-hour shingles (`ml/sagemaker/prepare_rcf_data.py`).
- Trained on data through 2008; alert thresholds from 2009 scores (out of sample).
- Confirmation run on SageMaker, validation Jan–May 2010: 1 RCF alert vs 37 log-MAD alerts under the
  same scheme. On injected x3 spikes at busy hours RCF caught 10.0 % vs 3.5 % for log-MAD.
- RCF is a weak detector on its own. It is kept because it flags some unusually large busy-hour values
  that log-MAD misses. The two detectors keep separate scores (`detector` field), with no merged severity.

### Inference

- Two serverless endpoints, `g2-greentrack-xgboost-serverless` and `g2-greentrack-rcf-serverless`,
  created only when `enable_endpoints = true`.
- `ml/inference/calibrate.py` writes `inference/params.json` (log-MAD statistics and both detectors'
  2009 reference scores) to the ML bucket, once.
- Lambda `g2-greentrack-ml-inference` (`ml/inference/handler.py`) returns the forecast and the anomaly
  scores of both detectors for a window of up to 7 days:

```json
{"start": "2010-01-24T00:00:00", "end": "2010-01-25T00:00:00"}
```

  Check run for 24 Jan 2010: 24 hourly predictions, log-MAD scored 24/24 hours, RCF 17/24 (the first
  hours are unscored because their 24-hour window contains an incomplete hour).
- `ml/inference/load_dynamodb.py` calls the Lambda week by week and writes the results to the app's
  `forecasts` and `anomalies` tables, which the API reads. For production pass
  `--forecasts-table g2-greentrack-production-forecasts --anomalies-table g2-greentrack-production-anomalies`.

### Cost and teardown

Spot training, serverless endpoints and small instance types. After the demo set
`enable_endpoints = false` and apply `infra/ml` again to remove the endpoints.
