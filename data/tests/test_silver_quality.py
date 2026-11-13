"""Tests for the silver Glue Data Quality rules (DATA-07): ruleset content and failure reporting."""
import pytest

pytest.importorskip("pyspark")

from data.jobs.silver_clean import DQ_RULESET, failed_rules  # noqa: E402


def test_ruleset_covers_null_rate_ranges_and_duplicates():
    for rule in ('Completeness "global_active_power"', 'where voltage < 200 or voltage > 260',
                 'IsUnique "timestamp"', 'IsComplete "timestamp"'):
        assert rule in DQ_RULESET


def test_failed_rules_lists_only_failures():
    outcomes = [
        {"Rule": 'IsUnique "timestamp"', "Outcome": "Passed", "FailureReason": None},
        {"Rule": 'Completeness "voltage" > 0.98', "Outcome": "Failed", "FailureReason": "Value: 0.95"},
    ]
    assert failed_rules(outcomes) == [('Completeness "voltage" > 0.98', "Value: 0.95")]
