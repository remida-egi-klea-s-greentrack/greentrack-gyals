"""Format grounded consumption results for the chat contract."""


def format_peak_response(peak: dict | None) -> dict:
    """Format a peak-query result without inventing measurements."""

    if peak is None:
        answer = (
            "No complete hourly consumption records were found "
            "for the requested interval."
        )
    else:
        answer = (
            f"Peak hourly consumption was "
            f"{peak['consumption_kwh']:.3f} kWh "
            f"for the hour starting {peak['timestamp']} "
            "(dataset timezone unspecified)."
        )

    return {
        "answer": answer,
        "citations": ["local_hourly_consumption_parquet"],
        "tools_used": ["find_peak_consumption"],
    }


def format_unsupported_response() -> dict:
    """Return a safe response for unsupported query types."""

    return {
        "answer": (
            "This local assistant currently supports only "
            "peak hourly consumption queries over an explicit "
            "date range."
        ),
        "citations": [],
        "tools_used": [],
    }
