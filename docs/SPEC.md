# SPEC: nyc-taxi-metrics

## 1. Purpose
A DuckDB + dbt pipeline over NYC TLC yellow taxi trips that produces tested, documented metrics and a static dashboard for a fictional stakeholder, the Head of Mobility Analytics.

Design priorities: correctness, testability, clarity, reproducibility. Out of scope: scale and cloud services.

## 2. Business questions
1. How do trips and revenue vary by hour of day, weekday and pickup borough?
2. How do average fare per mile and tip rate evolve month by month? (Tip rate is computed on credit-card trips only because cash tips are not recorded.)
3. After NYC congestion pricing started in January 2025, what share of trips carry `cbd_congestion_fee`, and how did Manhattan-pickup trips and fares change versus the months before? Descriptive only; state that it is not causal.

## 3. Data
- Yellow taxi trips, Parquet, one file per month: `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`
- Zone lookup, CSV: `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv`
- Default window: 2024-07 to 2025-06 (configurable). The `cbd_congestion_fee` column exists only from 2025 onward; the schema must handle files that lack it.
- The data has known quality issues (negative fares, dropoff before pickup, timestamps outside the file's month). Staging must filter or flag them with documented rules.
- Verify the URLs and file schemas before building. Raw downloads are never committed.

## 4. Architecture
`download (Python)` -> `DuckDB file (raw)` -> `dbt staging` -> `dbt marts` -> `static dashboard`

- Engine: DuckDB with dbt-duckdb. No servers, no cloud, no credentials.
- Python 3.12, virtualenv, pip. Runs on Windows 11 (PowerShell) and Ubuntu (CI): use pathlib, no bash-only scripts.

## 5. Requirements
### Ingestion
- `python run_pipeline.py [--start YYYY-MM --end YYYY-MM] [--sample]` runs download -> load -> `dbt build`.
- Idempotent: re-running never duplicates rows; already-loaded months are skipped unless `--force`.
- Downloads: retries with backoff, clear errors, row-count logging per month.
- `--sample` uses a committed fixture (`tests/fixtures/`, at most 2 MB, deterministic) and needs no network.

### dbt
- Layers: `staging` (views: typed, renamed, validated), `marts` (tables).
- Marts: `dim_zone`, `dim_date`, `fct_trips`, `fct_monthly_metrics`, plus any model the dashboard needs.
- `fct_trips` is incremental by month.
- Contracts enforced on every mart. At least 3 dbt unit tests covering the rules for fare, tip rate and invalid-trip filtering.
- Tests: not_null, unique, accepted_values, relationships, and a reconciliation test (raw rows = staging rows + rejected rows).
- Every model and column documented; metric definitions in `docs/metrics.md`.

### Dashboard
- Static site generated from the marts (preferred: Evidence; verify current docs and justify any alternative in `docs/decisions.md`).
- Pages: demand patterns, fare and tip trends, congestion-fee view. Each states its data window and caveats.

### CI (GitHub Actions)
- On pull requests: ruff, pytest, `run_pipeline.py --sample`, `dbt build`. No secrets required.

### Docs
- README: what it is, architecture diagram (Mermaid), how to run in 5 commands, findings (3 to 4, with method and limitations), design decisions, and a short section on how the project was built (spec-driven, with Claude Code, from docs/SPEC.md).
- `docs/decisions.md`: choices and rejected alternatives (e.g. why DuckDB, why not Spark).

## 6. Constraints
- Everything in English: code, comments, docs, commit messages.
- Never read, print or commit `.env` files or credentials. No cloud accounts. Network only to the public URLs above and package registries.
- Work on feature branches; conventional commits; never push to `main`.

## 7. Milestones and acceptance criteria
Milestones are delivered in order. A criterion counts as met only when the command has been run and its output recorded.

- **M1, pipeline and models:** in a fresh venv, `python run_pipeline.py --sample` exits 0; `cd dbt && dbt build` exits 0 with all tests passing; `python -m pytest` passes; `ruff check .` and `ruff format --check .` are clean.
- **M2, dashboard:** the site builds with one command, `docs/metrics.md` matches the models, and each of the three business questions has a page.
- **M3, CI and docs:** pull request checks are green; README, decisions and findings are complete.