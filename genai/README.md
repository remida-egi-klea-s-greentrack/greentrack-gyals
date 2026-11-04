# GreenTrack — Local GenAI Foundation (GENAI-01)

## Purpose

A local, deterministic data-query foundation for the future
Amazon Bedrock consumption assistant.

This is not yet a natural-language assistant.

## Implemented

- Read hourly electricity consumption from local Parquet.
- Filter incomplete, missing, nonfinite, and nonpositive readings.
- Find peak hourly consumption for an explicit date range.
- Select the earliest timestamp when peak values tie.
- Format grounded answers using the shared chat response fields.
- Reject unsupported query types without accessing data.

## Query semantics

- Start timestamp is inclusive; end timestamp is exclusive.
- Timestamps are timezone-naive, representing the start of an hour.
- No timezone conversion is performed.
- Consumption is measured in kWh.
- Empty valid-data intervals return no peak.

## Local usage

```python
from genai.dispatcher import dispatch_local_query

response = dispatch_local_query(
    query_type="peak_hourly_consumption",
    path="/path/to/hourly_consumption.parquet",
    start="2010-01-01",
    end="2010-01-02",
)
print(response)
```

The response contains `answer`, `citations`, and `tools_used`
as defined in `contracts/chat.json`.

## Testing

```bash
uv pip install -r genai/requirements-test.txt
python -m pytest genai/tests/ -q -W error
```

## Limitations and future integration

- No natural-language question interpretation.
- No conversation/session handling or HTTP endpoint.
- No Athena SQL, Bedrock model, or AWS credentials.
- Source citation is a local dataset identifier, not a document link.
- Input is a prepared local reference dataset, not yet the
  reproducible gold output of Developer A's pipeline.
- Production timestamp semantics require team agreement.

Future Challenge 4 work includes Bedrock tool calling, parameterized
read-only Athena queries, weekly reports, energy-saving guidance,
guardrails, and evaluation against expected answers.
