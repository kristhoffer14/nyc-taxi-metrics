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
