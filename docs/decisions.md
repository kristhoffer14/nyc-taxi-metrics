# Design decisions

Choices made while building the project, with the alternatives that were rejected.

## fct_trips is rebuilt when the staging rules change

**Problem.** `fct_trips` is incremental by month and used to reprocess a month only when
`raw.load_log.loaded_at` changed. Changing a staging rule (a threshold in `dbt_project.yml`
or the SQL in `stg_yellow_trips_classified`) left already-built months untouched, so
`fct_trips` silently disagreed with `stg_yellow_trips`. Reproduced on the sample database
by running with `max_trip_distance_miles: 1`: staging dropped to 755 and 764 rows for
2024-12 and 2025-01 while `fct_trips` kept 2945 and 2869.

**Decision.** `fct_trips` stores a `rules_hash` column: an MD5 of the two reject-threshold
variables plus the source of `stg_yellow_trips_classified`, `stg_yellow_trips` and
`stg_taxi_zones` (macro `staging_rules_hash`). A month is reprocessed when it is new,
when its `loaded_at` changed, or when its stored `rules_hash` differs from the current one.
The singular test `assert_fct_trips_matches_staging` compares per-month row counts of
`stg_yellow_trips` and `fct_trips` and fails if they ever diverge.

**Consequences.**
- Editing a rule, even whitespace in those models, rebuilds all months on the next
  `dbt build`. That is a few seconds on DuckDB and keeps the table correct.
- Adding the column changes the table schema (`on_schema_change='fail'`), so a database
  built before this change needs a one-off `dbt build --full-refresh` (or deleting the
  `.duckdb` file and rerunning the pipeline).
- The hash covers the rules, not `fct_trips.sql` itself. Changing the columns of
  `fct_trips` is caught by the contract and `on_schema_change='fail'`.

**Rejected alternatives.**
- *Always full-refresh `fct_trips`:* correct but defeats the incremental requirement in the spec.
- *Only `--full-refresh` from `run_pipeline.py` when it detects a change:* plain
  `cd dbt && dbt build` would still go stale.
- *Compare row counts to decide what to rebuild:* misses rule changes that keep the
  count the same, and needs a scan of staging on every run.
- *Hash only the variables:* misses edits to the rule SQL.

## Dashboard tool: Evidence (open-source build), reading Parquet

**Decision.** The dashboard is an Evidence project in `dashboard/`, built to static HTML with
`npm run build:strict`. The marts are exported to Parquet by `pipeline/export.py`, and Evidence
reads those files through an in-memory DuckDB source (`read_parquet(...)`).

**What was verified (2026-10-09).**
- `@evidence-dev/evidence` 40.1.8 and `@evidence-dev/duckdb` 2.0.1 are the current npm releases, MIT
  licensed and not marked deprecated. The GitHub repository is not archived.
- The current Evidence docs centre on the managed Evidence Studio. The open-source static build
  is documented under `legacy-docs.evidence.dev`, and the `legacy` branch of `evidence-dev/template`
  is the open-source scaffold. Nothing states that it will stop being maintained, but the "legacy"
  label is a risk for the long term.
- A spike on Windows 11 with Node 24.20.0 passed: `npm install`, `npm run sources` and
  `npm run build:strict` succeeded. The Ubuntu build is checked in M3 (CI).

**Gotchas found while building.**
- `@evidence-dev/evidence` 40.1.8 needs exactly `typescript@5.4.2` as a peer; npm otherwise picks
  TypeScript 7 and fails to resolve. It is pinned in `dashboard/package.json`.
- `build:strict` exits 0 even when a page query fails. `pipeline/dashboard.py` therefore scans
  Evidence's output for `Error in ...` and fails the build.
- `build` does not re-read the data; `sources:strict` must run first or a stale cache is used.
- Evidence sorts a categorical x-axis by the y value unless `sort=false` is set, which reordered
  months on the tip-rate chart. All time-ordered line charts set it.

**Why Parquet instead of the `.duckdb` file.** The connector bundles `@duckdb/node-api ^1.4.x`
while the pipeline writes DuckDB 1.5.5 files. Whether the older reader opens the newer file format
was not verified, and Parquet avoids the question. It also keeps the dashboard independent of dbt:
CI can build the site from the committed fixture without the Node side touching the database.

**Rejected alternatives.**
- *Python-only (Plotly or Altair with Jinja):* one toolchain and no Node, but it departs from the
  spec's preferred tool and means writing the page layout by hand. It remains the fallback if
  Evidence stops building.
- *Reading the `.duckdb` file directly:* fewer steps, but depends on the unverified format
  compatibility above.
- *Querying `fct_trips` from the dashboard:* puts untested SQL in the pages and scans every trip
  at build time. The dashboard reads only contract-tested marts (`fct_demand_hourly`,
  `fct_daily_congestion`, `fct_monthly_metrics`).
