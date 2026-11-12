"""Tests for DATA-01 bronze ingestion: raw data kept exactly, metadata added."""
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from data.jobs.bronze_ingest import ingest  # noqa: E402

RAW_TEXT = (
    "Date;Time;Global_active_power;Global_reactive_power;Voltage;Global_intensity;"
    "Sub_metering_1;Sub_metering_2;Sub_metering_3\n"
    "16/12/2006;17:24:00;4.216;0.418;234.840;18.400;0.000;1.000;17.000\n"
    "21/12/2006;11:23:00;?;?;?;?;?;?;\n"
    "1/1/2007;00:00:00;2.580;0.136;241.970;10.600;0.000;0.000;0.000\n"
)


@pytest.fixture
def bronze(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the script writes to data/lakehouse/... relative to here
    raw = tmp_path / "sample_power.txt"
    raw.write_text(RAW_TEXT)
    out_file = ingest(raw)
    return pd.read_parquet(tmp_path / out_file)


def test_keeps_every_row(bronze):
    assert len(bronze) == 3


def test_keeps_values_exactly_as_received(bronze):
    assert bronze.loc[0, "Voltage"] == "234.840"         # not converted to 234.84
    assert bronze.loc[1, "Global_active_power"] == "?"   # "?" is not turned into null
    assert bronze.loc[1, "Sub_metering_3"] == ""         # empty stays empty text
    assert bronze.loc[2, "Date"] == "1/1/2007"           # dates are not parsed


def test_adds_traceability_metadata(bronze):
    assert (bronze["source_file"] == "sample_power.txt").all()
    assert bronze["load_timestamp"].nunique() == 1
    assert pd.Timestamp(bronze.loc[0, "load_timestamp"]).tzinfo is not None  # UTC, with timezone


def test_output_named_after_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "new_batch.txt"
    raw.write_text(RAW_TEXT)
    out_file = ingest(raw)
    assert out_file.name == "new_batch.parquet"