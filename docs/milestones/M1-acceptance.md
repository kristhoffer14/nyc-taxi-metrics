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
