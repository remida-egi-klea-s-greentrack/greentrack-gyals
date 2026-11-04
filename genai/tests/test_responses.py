"""Tests for grounded chat response formatting."""

from genai.responses import format_peak_response


def test_successful_peak_response():
    peak = {
        "timestamp": "2010-01-01T16:00:00",
        "consumption_kwh": 2.8009333333333335,
    }

    result = format_peak_response(peak)

    assert set(result) == {
        "answer", "citations", "tools_used"
    }
    assert "2.801 kWh" in result["answer"]
    assert "2010-01-01T16:00:00" in result["answer"]
    assert "dataset timezone unspecified" in result["answer"]
    assert result["citations"] == [
        "local_hourly_consumption_parquet"
    ]
    assert result["tools_used"] == [
        "find_peak_consumption"
    ]


def test_no_data_response():
    result = format_peak_response(None)

    assert set(result) == {
        "answer", "citations", "tools_used"
    }
    assert "No complete hourly consumption records" in result["answer"]
    assert "kWh" not in result["answer"]
    assert result["tools_used"] == [
        "find_peak_consumption"
    ]


def test_unsupported_query_response():
    from genai.responses import format_unsupported_response

    result = format_unsupported_response()

    assert set(result) == {
        "answer", "citations", "tools_used"
    }
    assert "only peak hourly consumption" in result["answer"]
    assert result["citations"] == []
    assert result["tools_used"] == []
