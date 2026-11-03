"""Unit tests for the local global log-MAD anomaly baseline."""

import numpy as np
import pandas as pd
import pytest

from ml.anomaly.global_log_mad import GlobalLogMADDetector


@pytest.fixture
def train():
    # 32 weeks: at least 30 observations per hour-of-week group.
    index = pd.date_range("2008-01-07", periods=32 * 168, freq="h")
    weeks = np.arange(len(index)) // 168
    how = np.asarray(index.day_of_week * 24 + index.hour)
    kwh = 0.4 + 0.01 * how + 0.03 * weeks
    return pd.Series(kwh, index=index)


def test_fit_and_score_every_hour(train):
    detector = GlobalLogMADDetector().fit(train)
    result = detector.score(train)

    assert len(detector.medians_) == len(detector.mads_) == 168
    assert len(result) == len(train)
    assert result["timestamp"].tolist() == list(train.index)
    assert result["anomaly_score"].between(0, 1).all()
    assert set(result["severity"].dropna()).issubset(
        {"low", "medium", "high"}
    )


def test_normal_observation_is_not_alerted(train):
    detector = GlobalLogMADDetector().fit(train)
    typical = np.exp(detector.medians_.loc[0])
    probe = pd.Series(
        [typical], index=[pd.Timestamp("2010-01-04 00:00")]
    )

    row = detector.score(probe).iloc[0]

    assert row["robust_z"] == pytest.approx(0, abs=1e-12)
    assert row["severity"] is None


def test_extreme_high_and_low_are_high_severity(train):
    detector = GlobalLogMADDetector().fit(train)
    typical = np.exp(detector.medians_.loc[0])

    probe = pd.Series(
        [typical * np.exp(40), typical * np.exp(-40)],
        index=[
            pd.Timestamp("2010-01-04"),
            pd.Timestamp("2010-01-11"),
        ],
    )

    result = detector.score(probe)

    assert result["severity"].tolist() == ["high", "high"]
    assert result["anomaly_score"].tolist() == [1.0, 1.0]
    assert result["robust_z"].iloc[0] > 0
    assert result["robust_z"].iloc[1] < 0


def test_incomplete_hours_remain_unscored(train):
    detector = GlobalLogMADDetector().fit(train)

    probe = pd.Series(
        [1.0, np.nan, 1.5],
        index=pd.date_range("2010-01-04", periods=3, freq="h"),
    )
    result = detector.score(probe)

    assert len(result) == 3
    assert pd.isna(result.loc[1, "anomaly_score"])
    assert pd.isna(result.loc[1, "severity"])
    assert result.loc[[0, 2], "anomaly_score"].notna().all()


def test_future_observation_does_not_change_earlier_score(train):
    detector = GlobalLogMADDetector().fit(train)

    first = pd.Series(
        [1.0], index=[pd.Timestamp("2010-01-04")]
    )
    extended = pd.Series(
        [1.0, 1e20],
        index=pd.date_range("2010-01-04", periods=2, freq="h"),
    )

    one = detector.score(first).iloc[0]
    two = detector.score(extended).iloc[0]

    assert one["robust_z"] == pytest.approx(two["robust_z"])
    assert one["anomaly_score"] == two["anomaly_score"]
    assert one["severity"] == two["severity"]


def test_insufficient_training_coverage_fails(train):
    with pytest.raises(ValueError, match="at least 30"):
        GlobalLogMADDetector().fit(train.iloc[:29 * 168])


def test_zero_mad_fails(train):
    how = train.index.day_of_week * 24 + train.index.hour
    constant = pd.Series(
        0.5 + np.asarray(how) * 0.01,
        index=train.index,
    )

    with pytest.raises(ValueError, match="MAD must be positive"):
        GlobalLogMADDetector().fit(constant)


def test_scoring_before_fit_fails(train):
    with pytest.raises(ValueError, match="Fit the detector"):
        GlobalLogMADDetector().score(train.iloc[:1])


@pytest.mark.parametrize("bad_value", [0.0, -1.0, np.inf])
def test_invalid_consumption_fails(train, bad_value):
    bad = train.copy()
    bad.iloc[0] = bad_value

    with pytest.raises(ValueError, match="finite and positive"):
        GlobalLogMADDetector().fit(bad)
