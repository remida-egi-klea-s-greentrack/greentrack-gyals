"""Route explicitly typed local consumption queries."""

from pathlib import Path

from genai.queries import find_peak_consumption
from genai.responses import (
    format_peak_response,
    format_unsupported_response,
)


def dispatch_local_query(
    query_type: str,
    path: str | Path,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Execute a supported read-only query and format its result."""

    if query_type != "peak_hourly_consumption":
        return format_unsupported_response()

    if not start or not end:
        raise ValueError(
            "peak_hourly_consumption requires start and end"
        )

    peak = find_peak_consumption(path, start, end)
    return format_peak_response(peak)
