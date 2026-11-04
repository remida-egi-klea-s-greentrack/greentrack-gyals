# GreenTrack — Team Plan, Tasks & Milestones

**As of 2 November 2026** · Based on the team's original developer-allocation plan, current public GitHub PRs, and the verified independent local demonstration.

[← Project README](README.md) · [Architecture and dependencies](ARCHITECTURE.md)

## Status key and issue-number caveat

- **Merged:** code is present in the shared repository's main branch.
- **Verified local:** tested in a local development environment or prepared demo, **not necessarily on main**.
- **Open PR:** code proposed for integration; not treated as merged.
- **Partial:** some deliverables exist, but the task's full acceptance criteria are not yet met.
- **Pending:** not verified as implemented.
- **AWS planned:** cloud resource/integration not deployed.

> **Important task-ID mismatch:** The original screenshots assigned `ML-02` to XGBoost, `ML-03` to anomalies, `ML-04` to mocked SageMaker calls, and `ML-05` to AWS SageMaker. Actual GitHub work instead uses **ML-02 = rolling evaluation, ML-03 = XGBoost, ML-04 = anomaly detection**. A later **local “ML-05” statistical model-selection experiment** is also separate from the screenshot's **AWS ML-05**. The tables below use **current GitHub IDs where they exist** and label unmatched items as *planned*—do not create duplicate GitHub issues based on the old IDs.

## Milestones

| Milestone | Expected demonstration | Current assessment |
| --- | --- | --- |
| **M1 — Local data foundation** | UCI raw → Bronze → Silver Iceberg → validated Gold | **Achieved locally** with real Glue 5 Docker/PySpark jobs |
| **M2 — Fully integrated local application** | Docker-run app, real Gold data and ML outputs, mock SageMaker/Bedrock where necessary, stable contracts | **Partial.** Separate working Streamlit/API demo; team React/DynamoDB/backend Docker integration not yet complete |
| **M3 — Managed AWS deployment** | HTTPS React app; S3/Glue/Athena, SageMaker and Bedrock; Terraform and GitHub Actions/OIDC | **Not deployed** |

## Developer A — Data Engineering

**Owns:** Challenge 2 and the Gold-data / SQL tool foundations consumed by Developer B and C.

| Task | Environment | Deliverable | Status / evidence |
| --- | --- | --- | --- |
| **DATA-01** | LOCAL | Preserve UCI input, Bronze Parquet and source/load metadata | **Partial / locally processed.** Bronze ingestion verified; validate exact ingestion metadata against committed job before closing all acceptance criteria |
| **DATA-02** | LOCAL | PySpark cleaning: timestamps, nulls, types, duplicates → Silver Iceberg | **Merged** in [PR #14](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/14); executed with Glue 5 Docker locally |
| **DATA-03** | LOCAL | Gold hourly/daily/peak/submetering tables and quality assertions | **Merged** in [PR #15](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/15); local Gold outputs independently checked |
| **DATA-04** | LOCAL | Iceberg incremental upsert, time travel and local analytical SQL tests | **Pending verification** |
| **DATA-05** | LOCAL + MOCK | Repeatable pipeline runner and simulated file-arrival/S3 boundary tests | **Pending verification**; manual/local execution does not itself prove triggered automation |
| **DATA-06** | AWS | Terraform S3 Bronze/Silver/Gold, Glue jobs and catalog, Athena queries | **AWS planned** |
| **DATA-07** | AWS | Glue Data Quality, Lake Formation, EventBridge/Step Functions; Athena Iceberg upserts/time travel | **AWS planned** |

**M2 handoff:** a reproducible local Gold pipeline and data contract usable by ML and app without AWS. **M3 handoff:** same processing logic operating on managed AWS resources with proper governance.

## Developer B — ML & GenAI

**Owns:** Challenges 3 and 4; forecasting, anomaly scoring, ML evaluation, assistant tool boundaries, later SageMaker and Bedrock modules.

### Actual implemented / tracked work

| Work item | Environment | Deliverable | Status / evidence |
| --- | --- | --- | --- |
| **ML-01** | LOCAL | Daily/weekly seasonal naive forecasting | **Merged** in [PR #3](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/3) |
| **ML-02** | LOCAL | Rolling 24h forecast evaluation, metrics and exclusions | **Integrated** through [PR #13](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/13) (original stacked [PR #5](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/5)) |
| **ML-03** | LOCAL | XGBoost forecasting with lag/calendar features and benchmark | **Verified local; open [PR #7](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/7)** |
| **ML-04** | LOCAL | Global log-MAD anomaly baseline and evaluation | **Verified local; open [PR #9](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/9)**; not Random Cut Forest |
| **GENAI-01** | LOCAL | Deterministic peak-hour query over complete Gold readings | **Verified local**, tracked in [issue #10](https://github.com/remidacollaku5-dot/greentrack-gyals/issues/10); not a general language assistant |
| **Local statistical benchmark** | LOCAL | ETS preflight, frozen-seasonality MSTL + SES benchmark and model selection | **Completed in separate demo workspace.** XGBoost retained; **not** the AWS ML-05 task in the original plan |
| **Final held-out assessment** | LOCAL | Freeze chosen XGBoost, evaluate once on reserved test period | **Completed in separate demo workspace**: 0.5653 kWh test RMSE on 3,456 hours; no test-time retuning |

### Original plan work still outstanding

| Original plan label | Environment | Deliverable | Status |
| --- | --- | --- | --- |
| *ML-04 mock integration* | LOCAL + MOCK | Forecast/anomaly service contract; botocore Stubber-based SageMaker `InvokeEndpoint` simulation | **Pending**; standalone local API is not proof of SageMaker API stubbing |
| *AI-01* | LOCAL + MOCK | Tool orchestration, allowlisted read-only SQL, weekly report, mocked Bedrock tool calls | **Partial foundation:** deterministic peak lookup only; SQL/LLM/report orchestration pending |
| *AI-02* | LOCAL + MOCK | Energy-efficiency source corpus, retrieval/citation tests, 15–20 QA evaluations, simulated Knowledge Base | **Pending** |
| *ML-05 AWS (original plan)* | AWS | SageMaker Pipeline, built-in Random Cut Forest, Model Registry, endpoint, Lambda caller | **AWS planned**; not the local statistical ML-05 experiment |
| *AI-03* | AWS | Bedrock Claude, live Athena tools, S3 Vectors Knowledge Base, Guardrails and evaluation | **AWS planned** |

**M2 handoff:** tested forecasting/anomaly predictions plus safe, data-grounded query contracts (original milestone also requests a simulated LLM chat; that part is not complete). **M3 handoff:** registered SageMaker models and a functioning Bedrock assistant.

## Developer C — Application & DevOps

**Owns:** Challenge 1, the team's local development experience, frontend/backend integration, GitHub workflows, and coordination of Terraform integration.

| Task | Environment | Deliverable | Status / evidence |
| --- | --- | --- | --- |
| **APP-01** | LOCAL | Repository structure, Compose, issue/PR workflow, basic CI | **Partial / scaffold exists.** Current Compose defines DynamoDB Local only, not full one-command application startup |
| **APP-02** | LOCAL + MOCK | Lambda-compatible REST handlers for `/consumption`, `/anomalies`, `/forecast`, `/chat` | **Open [PR #16](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/16)**; review input validation, fixture/schema alignment and tests before merge |
| **APP-03** | LOCAL | DynamoDB Local tables, keys, seeded records, access tests | **Partial:** DynamoDB Local container configured; seeded tables and access tests not verified |
| **APP-04** | LOCAL | React dashboard, anomaly list, forecast charts and chat panel against fixtures | **Pending in the shared app**; separate Streamlit demo is not the React deliverable |
| **APP-05** | LOCAL + MOCK | Integrate real Gold and local ML outputs; mock SageMaker/Bedrock where necessary | **Pending in the shared app**; separate Streamlit demo proves component feasibility |
| **APP-06** | LOCAL | Terraform modules, CI tests, one-command Docker-based local demo | **Partial:** CI scaffold and DynamoDB service; Terraform/full Docker demo not verified |
| **APP-07** | AWS | Remote Terraform state, OIDC/IAM/secrets, S3/CloudFront, Lambda/API Gateway and DynamoDB | **AWS planned** |
| **APP-08** | AWS | CI/CD Terraform plan/apply and app deploy, real E2E deployment and teardown tests | **AWS planned** |

**M2 handoff:** complete locally runnable Docker application reading actual processed data and ML results. **M3 handoff:** HTTPS app deployed and updated by GitHub Actions.

## Cross-team dependencies and acceptance checks

| Dependency | Responsible people | Agreed output |
| --- | --- | --- |
| Gold data → Forecasting | A → B | Timestamped hourly consumption, known units, completeness and missing-data policy |
| Gold data → Application | A → C | Aggregated consumption schema; coordinate anomaly response records with B |
| Forecasting → Application | B → C | 24-hour forecast and anomaly response schemas |
| SQL tools → Assistant | A + B | Bounded, parameterized, read-only queries with evidence |
| Bedrock → Chat endpoint | B + C | Assistant request/response contract and error behavior |
| Terraform deployment | A + B + C | Shared state strategy, per-owner modules, correct IAM roles; C coordinates |

## Immediate integration priorities

1. **Protect the working artifacts.** Keep the independently verified Gold data, model checkpoints and final held-out report intact; never copy them wholesale into Git.
2. **Review pending PRs.** Integrate [ML #7](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/7), [ML #9](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/9) and [APP #16](https://github.com/remidacollaku5-dot/greentrack-gyals/pull/16) only after teammate review, compatibility checks and passing CI.
3. **Agree contracts.** Cross-check Gold `minutes_recorded`/`complete`, anomaly percentile/severity, forecast 24-hour timestamps, and `/chat` versus local `/query`.
4. **Complete M2 integration.** Make the team app runnable from a fresh clone, consuming real Gold and ML outputs; add contract and integration tests. The Streamlit demo is an example, not a substitute for the planned React deliverable.
5. **Plan M3 separately.** Terraform modules for A/B/C and GitHub OIDC must be reviewed; deploy managed AWS services only when account access, cost controls and acceptance tests are ready.

## Collaboration rules

- Work in issue-scoped branches; no direct pushes to `main`.
- Use small PRs, at least one teammate review, passing CI, and updated fixtures/contracts when interfaces change.
- Treat an open PR or a completed independent demo as distinct from code merged on `main`.
- Run and document tests and data provenance. Do not use the final held-out test set to tune models.
- Do not commit secrets, raw data, local checkpoints, generated reports or virtual environments to the shared repo without a reviewed retention/distribution policy.

[← Project README](README.md) · [Architecture and dependencies](ARCHITECTURE.md)
