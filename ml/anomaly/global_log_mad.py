"""Global hour-of-week log-MAD anomaly detector (local baseline)."""

import numpy as np
import pandas as pd


def _validated_values(consumption: pd.Series) -> pd.Series:
    if not isinstance(consumption, pd.Series):
        raise TypeError("Expected a pandas Series")

    index = consumption.index
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("Expected a DatetimeIndex")
    if index.has_duplicates or index.hasnans or not index.is_monotonic_increasing:
        raise ValueError("Timestamps must be unique, non-null, and sorted")
    if index.tz is not None or not (index == index.floor("h")).all():
        raise ValueError("Expected timezone-naive whole-hour timestamps")

    values = consumption.astype(float)
    valid = values.dropna()

    if not np.isfinite(valid.to_numpy()).all() or (valid <= 0).any():
        raise ValueError("Observed consumption must be finite and positive")

    return values


def _hour_of_week(index: pd.DatetimeIndex):
    return index.day_of_week * 24 + index.hour


class GlobalLogMADDetector:
    """Rank unusual consumption against training deviations."""

    def fit(self, consumption: pd.Series):
        values = _validated_values(consumption).dropna()
        groups = _hour_of_week(values.index)
        logged = np.log(values)
        grouped = logged.groupby(groups)

        counts = grouped.size().reindex(range(168), fill_value=0)
        if (counts < 30).any():
            raise ValueError(
                "Need at least 30 valid observations per hour-of-week group"
            )

        medians = grouped.median().reindex(range(168))
        mads = grouped.apply(
            lambda s: (s - s.median()).abs().median()
        ).reindex(range(168))

        if mads.isna().any() or (mads <= 0).any():
            raise ValueError("MAD must be positive in every group")

        typical = medians.loc[groups].to_numpy()
        scale = 1.4826 * mads.loc[groups].to_numpy()

        deviations = np.abs(logged.to_numpy() - typical) / scale

        self.medians_ = medians
        self.mads_ = mads
        self.training_deviations_ = np.sort(deviations)

        return self

    def score(self, consumption: pd.Series) -> pd.DataFrame:
        if not hasattr(self, "training_deviations_"):
            raise ValueError("Fit the detector before scoring")

        values = _validated_values(consumption)

        result = pd.DataFrame({
            "timestamp": values.index,
            "consumption_kwh": values.to_numpy(),
            "robust_z": np.nan,
            "anomaly_score": np.nan,
            "severity": [None] * len(values),
        })

        valid = values.dropna()
        if valid.empty:
            return result

        groups = _hour_of_week(valid.index)

        z = (
            np.log(valid.to_numpy())
            - self.medians_.loc[groups].to_numpy()
        ) / (
            1.4826 * self.mads_.loc[groups].to_numpy()
        )

        # Percentile relative to training deviations, not a probability.
        percentile = (
            np.searchsorted(
                self.training_deviations_,
                np.abs(z),
                side="right",
            )
            / len(self.training_deviations_)
        )

        severity = np.full(len(valid), None, dtype=object)
        severity[percentile >= 0.99] = "low"
        severity[percentile >= 0.995] = "medium"
        severity[percentile >= 0.999] = "high"

        present = values.notna().to_numpy()

        result.loc[present, "robust_z"] = z
        result.loc[present, "anomaly_score"] = percentile
        result.loc[present, "severity"] = severity

        return result
