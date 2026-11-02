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
