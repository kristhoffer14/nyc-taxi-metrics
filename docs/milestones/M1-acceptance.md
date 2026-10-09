# Milestone 1: acceptance record

This file records the evidence for Milestone 1 (see `docs/SPEC.md`, section 7).

## Source verification (2026-10-09)

All three URLs from the spec resolved (HTTP 200) and downloaded into `data/raw/` (git-ignored).

| File | Size | Rows |
|---|---|---|
| `yellow_tripdata_2024-12.parquet` | 61.5 MB | 3,668,371 |
| `yellow_tripdata_2025-01.parquet` | 59.2 MB | 3,475,226 |
| `taxi_zone_lookup.csv` | 12 KB | 265 |

### Trip file schema (as reported by DuckDB 1.5.5)

| Column | Type | Notes |
|---|---|---|
| VendorID | INTEGER | values 1, 2, 6, 7 |
| tpep_pickup_datetime | TIMESTAMP | |
| tpep_dropoff_datetime | TIMESTAMP | |
| passenger_count | BIGINT | NULL when payment_type = 0 |
| trip_distance | DOUBLE | |
| RatecodeID | BIGINT | 99 = unknown; NULL when payment_type = 0 |
| store_and_fwd_flag | VARCHAR | |
| PULocationID | INTEGER | |
| DOLocationID | INTEGER | |
| payment_type | BIGINT | 0 to 5 observed |
| fare_amount .. total_amount | DOUBLE | |
| congestion_surcharge | DOUBLE | NULL when payment_type = 0 |
| Airport_fee | DOUBLE | capitalised in the file |
| cbd_congestion_fee | DOUBLE | **2025-01 only**; absent from 2024-12; can be negative (-0.75) |

### Zone lookup schema

`LocationID BIGINT, Borough VARCHAR, Zone VARCHAR, service_zone VARCHAR`. 265 distinct IDs.
Boroughs: Bronx, Brooklyn, EWR, Manhattan, N/A, Queens, Staten Island, Unknown
(264 = Unknown, 265 = N/A / Outside of NYC).

### Observed quality issues

| Issue | 2024-12 | 2025-01 |
|---|---|---|
| fare_amount < 0 | 78,444 | 144,118 |
| total_amount < 0 | 70,496 | 63,037 |
| dropoff <= pickup | 1,223 | 2,051 |
| pickup outside the file's month | 34 | 22 |
| trip_distance <= 0 | 75,450 | 90,893 |
| trip_distance > 100 mi | 129 | 162 |

These drive the staging rules documented in `dbt/models/staging/_staging.yml`.

The remaining months in the default window were not downloaded in M1. The loader matches
columns by name, case-insensitively, and fills missing optional columns with NULL, so
schema drift fails loudly only if a required column disappears.

## Real-data ingestion check (2026-10-09)

`python run_pipeline.py --start 2024-12 --end 2025-01`, run three times against
`data/nyc_taxi.duckdb` (dbt target `dev`).

| Run | Flags | Exit | Time | Load result | dbt build |
|---|---|---|---|---|---|
| 1 | (none) | 0 | 28 s | both months loaded | PASS=53 ERROR=0 |
| 2 | (none) | 0 | 15 s | both months skipped (already loaded) | PASS=53 ERROR=0 |
| 3 | `--force` | 0 | 30 s | files re-downloaded, both months replaced | PASS=53 ERROR=0 |

Row counts were identical after runs 2 and 3 (no duplicates), and raw counts equal
the source files exactly:

| Month | Raw | Valid (stg / fct_trips) | Rejected | Raw = valid + rejected |
|---|---|---|---|---|
| 2024-12 | 3,668,371 | 3,587,961 | 80,410 | yes |
| 2025-01 | 3,475,226 | 3,328,570 | 146,656 | yes |

Rejected rows by rule:

| Rule | 2024-12 | 2025-01 |
|---|---|---|
| negative_amount | 79,020 | 144,439 |
| non_positive_duration | 1,217 | 2,040 |
| invalid_distance | 121 | 137 |
| pickup_outside_source_month | 34 | 22 |
| excessive_duration | 18 | 18 |
| unknown_zone, missing_required_value | 0 | 0 |

`fct_monthly_metrics` on real data (a smoke check; findings belong to M2/M3):

| Month | Trips | Fare per mile | Tip rate | CBD fee share | Manhattan pickups | Manhattan avg fare |
|---|---|---|---|---|---|---|
| 2024-12 | 3,587,961 | $6.13 | 22.0% | n/a | 3,186,632 | $17.01 |
| 2025-01 | 3,328,570 | $5.75 | 22.8% | 65.6% | 2,967,151 | $14.78 |

## M1 acceptance run (2026-10-09)

Environment: Windows 11, PowerShell, Python 3.12.10. A fresh clone of
`feat/m1-pipeline` at `e81ff73` into an empty directory, a new venv, then
`pip install -r requirements-dev.txt` (duckdb 1.5.5, dbt-core 1.12.5,
dbt-duckdb 1.11.0, requests 2.34.2, pytest 9.1.1, ruff 0.16.9).

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `python run_pipeline.py --sample` | 0 | 2 months x 3,012 rows loaded; dbt `PASS=53 WARN=0 ERROR=0 SKIP=0` |
| 2 | `cd dbt; dbt build` | 0 | `Completed successfully`, `PASS=53 WARN=0 ERROR=0 SKIP=0` |
| 3 | `python -m pytest` | 0 | `32 passed in 13.92s` |
| 4 | `ruff check .` / `ruff format --check .` | 0 / 0 | `All checks passed!` / `20 files already formatted` |

dbt build covers 4 view models, 3 table models, 1 incremental model, 41 data tests
(including the raw = valid + rejected reconciliation) and 4 unit tests (reject
rules, fare per mile, tip rate, CBD fee share). After the run, `git status` in the
clone was empty: every output (`data/`, `dbt/target/`, logs) is git-ignored.

Output excerpts:

```text
### 1. python run_pipeline.py --sample
INFO pipeline: Sample mode: loading 2024-12, 2025-01 from ...\tests\fixtures
INFO pipeline:   2024-12:       3012 rows  loaded
INFO pipeline:   2025-01:       3012 rows  loaded
Finished running 1 incremental model, 3 table models, 41 data tests, 4 unit tests, 4 view models in 0 hours 0 minutes and 3.16 seconds (3.16s).
Done. PASS=53 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=53
INFO pipeline: Pipeline finished: ...\data\sample.duckdb
exit=0

### 2. cd dbt; dbt build
Finished running 1 incremental model, 3 table models, 41 data tests, 4 unit tests, 4 view models in 0 hours 0 minutes and 1.86 seconds (1.86s).
Completed successfully
Done. PASS=53 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=53
exit=0

### 3. python -m pytest
============================= 32 passed in 13.92s =============================
exit=0

### 4a. ruff check .
All checks passed!
exit=0

### 4b. ruff format --check .
20 files already formatted
exit=0
```

**Status: all Milestone 1 acceptance criteria met.**

## Review-fix acceptance run (2026-10-09)

Four review findings were fixed on `feat/m1-pipeline`: stale `fct_trips` after a staging
rules change (`rules_hash` plus `assert_fct_trips_matches_staging`, see `docs/decisions.md`),
retries for dropped downloads and a clean CLI error, a loader warning for missing optional
columns plus `--show-schema`, and metric shares recomputed on valid trips.

Environment: Windows 11, PowerShell, Python 3.12. A fresh clone of `feat/m1-pipeline` at
`5f44748` into an empty directory, a new venv, then `pip install -r requirements-dev.txt`.

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `python run_pipeline.py --sample` | 0 | 2 months x 3,012 rows loaded; dbt `PASS=54 WARN=0 ERROR=0 SKIP=0` |
| 2 | `cd dbt; dbt build` | 0 | `Completed successfully`, `PASS=54 WARN=0 ERROR=0 SKIP=0` |
| 3 | `python -m pytest` | 0 | `40 passed in 35.24s` |
| 4 | `ruff check .` / `ruff format --check .` | 0 / 0 | `All checks passed!` / `21 files already formatted` |

The build now has 42 data tests (one more: `assert_fct_trips_matches_staging`). After the
run, `git status` in the clone was empty. Run 1 logged the new warning for the one sample
month without the column: `yellow_tripdata_2024-12.parquet: optional column
cbd_congestion_fee is missing; loading it as NULL`.

### Stale fct_trips: reproduction

On the sample database with `--vars '{max_trip_distance_miles: 1}'`, `dbt run` left
`fct_trips` at 2,945 (2024-12) and 2,869 (2025-01) rows while `stg_yellow_trips` had 755 and
764. The new test failed with `Got 2 results`. After the fix, the same sequence rebuilds
both months and the test passes; a rerun with default variables rebuilds them again.

### Schema of every month in the default window

`python run_pipeline.py --show-schema` (downloads the 12 files, touches no database):

| Months | Columns | Missing required | Missing optional | Unexpected | Type differences |
|---|---|---|---|---|---|
| 2024-07 to 2024-12 | 19 | none | `cbd_congestion_fee` | none | none |
| 2025-01 to 2025-06 | 20 | none | none | none | none |

All 12 months load with the current schema. `cbd_congestion_fee` is NULL for 2024-07 to
2024-12 and populated from 2025-01, as the spec expects.

**Status: all four acceptance commands pass after the review fixes.**
