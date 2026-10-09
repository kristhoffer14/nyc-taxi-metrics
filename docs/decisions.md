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
