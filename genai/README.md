# GreenTrack — Energy Assistant (Challenge 4)

A natural-language assistant on Amazon Bedrock over the household's consumption data. It answers
questions from live Athena queries on the Gold tables, writes a weekly report, and gives
energy-saving advice that cites its sources.

## How it works

- **Lambda** `g2-greentrack-assistant` (`genai/assistant/handler.py`), behind `POST /chat` on the app's
  API Gateway. The frontend chat panel calls it.
- **Model**: Claude on Bedrock (Converse API with tool calling, `eu.` inference profile), at most
  6 model turns per question (`genai/assistant/agent.py`).
- **Infrastructure**: Terraform in `infra/modules/genai`, applied from `infra/ml`.

Events:

```json
{"message": "Why was usage high last Tuesday evening?", "session_id": "abc"}
{"report": "weekly", "week_start": "2010-11-15"}
```

A chat reply has `answer`, `citations` and `tools_used` (`contracts/chat.json`); a report reply has
`report`, `citations` and `tools_used`.

## Tools

| Tool | What it returns |
| --- | --- |
| `consumption_summary` | Total and average kWh and data completeness for a period |
| `daily_consumption` | kWh per day (at most 62 days) |
| `peak_hours` | The highest-consumption hours (top 1–10) |
| `weekday_vs_weekend` | Average hourly kWh on weekdays vs weekends |
| `hourly_profile` | Average kWh for each hour of the day |
| `submetering_breakdown` | Kitchen, laundry, water heater and AC, and everything else |
| `forecast_and_anomalies` | Day-ahead forecast and both anomaly detectors, from the ML inference Lambda (at most 7 days) |
| `energy_saving_advice` | Passages from the Knowledge Base, each with its source document |

The SQL tools are **read-only and allowlisted**: the model never writes SQL. It picks a tool and
gives dates; the code checks them (format, order, inside the data range 2006-12-16 to 2010-11-26,
per-tool day limits, `top_n` 1–10) and fills them into a fixed `SELECT` template in
`genai/assistant/tools.py`. Requests to change data have no tool and are refused.

## Weekly report

`weekly_report` runs fixed tool calls (no free-form tool use): totals for the week and the week
before, daily consumption, peak hours, sub-metering, forecast and anomalies. Forecast vs actual
error and the sub-metering shares are computed in code, so the model only writes the text around
numbers it is given. Dates are inclusive; timestamps have no time zone (as in the dataset).

## Energy-saving advice (Knowledge Base)

- Knowledge Base `g2-greentrack-energy-guidance`, vector store **Amazon S3 Vectors** (1024 dimensions,
  cosine), embeddings Titan Text Embeddings v2 (`infra/modules/genai/knowledge_base.tf`).
- Corpus: 6 short guidance documents in `genai/knowledge_base/docs/` (water heating, laundry,
  kitchen, heating and cooling, standby power, reading your data), each with a `.metadata.json`
  with its title and public source URL. Answers that use them cite those sources.

## Safety

- **Bedrock Guardrails** on every model call: prompt-attack filter; hate, insults, sexual, violence
  and misconduct filters (medium); denied topics: programming help, politics, investment advice,
  medical and legal advice.
- Only the user's own text is assessed by the guardrail (`guardContent`); the assistant's own
  instructions are not, because the prompt-attack filter also fired on them.
- The system prompt limits the assistant to this household's data; other questions get a fixed refusal.
- Read-only tools only, as above.

## Evaluation

`genai/eval/run_eval.py` asks the **deployed** assistant 20 questions. Expected numbers come from
separate SQL on the Gold table (not the tool templates), so a wrong tool, wrong dates or a misread
result fail the case. Cases also cover refusals (out of scope and write-style requests) and
citations for advice.

```bash
PYTHONPATH=. python -m genai.eval.run_eval --out genai/eval/results.json
```

Result on the final code: **20/20 passed**.

## Tests

```bash
uv pip install -r genai/requirements-test.txt
python -m pytest genai/tests/ -q -W error
```

Unit tests run without AWS (Bedrock, Athena and Lambda clients are injected).

## Local foundation (GENAI-01)

`genai/queries.py`, `genai/dispatcher.py` and `genai/responses.py` are the earlier, deterministic
local version: one typed query (`peak_hourly_consumption`) over a local Parquet file, with the same
response fields. They are kept for local development and tests; the deployed assistant does not use them.

## Limitations

- One household (the UCI dataset); data ends on 2010-11-26.
- Timestamps have no time zone; no conversion is done.
- Citations list the documents the Knowledge Base returned, which can include one that the answer did not use.
- Bedrock AgentCore (optional stretch) is not used; the agent loop runs in the Lambda.
