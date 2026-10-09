# Metric definitions

All metrics are computed from valid trips only: rows of `stg_yellow_trips`, i.e. raw
trips that pass every staging rule (listed on `stg_yellow_trips_classified` in
`dbt/models/staging/_staging.yml`). Rejected trips are kept in
`stg_yellow_trips_rejected` for auditing.

Monthly metrics live in `marts.fct_monthly_metrics`, one row per source month
(`year_month`). A trip belongs to the month of the file it came from; staging rejects
trips whose pickup falls outside that month, so this equals the pickup month.

Ratio metrics are **ratios of sums**, not means of per-trip ratios. They weight each
trip by its size and are not distorted by very short trips with extreme per-trip ratios.

| Metric | Column | Definition | Population |
|---|---|---|---|
| Trips | `trips` | `count(*)` | Valid trips |
| Revenue (USD) | `revenue_usd` | `sum(total_amount)` | Valid trips |
| Fare per mile (USD) | `fare_per_mile_usd` | `sum(fare_amount) / sum(trip_distance_miles)` | Valid trips with `trip_distance_miles > 0` |
| Credit-card trips | `credit_card_trips` | `count(*)` | Valid trips with `payment_type = 1` and `fare_amount > 0` |
| Tip rate | `tip_rate` | `sum(tip_amount) / sum(fare_amount)` | Same as credit-card trips |
| Congestion pricing month | `is_congestion_pricing_month` | `year_month >= '2025-01'` | - |
| CBD fee trip share | `cbd_fee_trip_share` | `count(*) filter (where cbd_congestion_fee_amount > 0) / count(*)`; NULL before 2025-01 | Valid trips |
| Manhattan pickups | `manhattan_pickup_trips` | `count(*)` | Valid trips whose pickup zone's borough is Manhattan |
| Manhattan average fare (USD) | `manhattan_pickup_avg_fare_usd` | `sum(fare_amount) / count(*)` | Same as Manhattan pickups |

## Notes and caveats

- **Revenue** is `total_amount`: everything charged to the rider, including fare,
  surcharges, taxes, tolls, fees and card tips, but not cash tips (which the TLC does
  not record). The spec does not define revenue; this is the project's choice.
- **Fare** is `fare_amount`, the time-and-distance meter fare, excluding extras,
  tolls, taxes, fees and tips.
- **Tip rate** uses credit-card trips only because cash tips are not recorded, and
  divides by `fare_amount` rather than the total, so tolls and fees do not dilute it.
  Trips with zero fare are excluded so a tip on a no-fare trip cannot inflate it.
- **Fare per mile** excludes zero-distance trips (kept as valid trips; 2.1% of rows in 2024-12 and
  2.6% in 2025-01), which have no meaningful per-mile price.
- **CBD fee share** is NULL, not zero, before January 2025: the fee did not exist and
  files before 2025 have no `cbd_congestion_fee` column. Tolling began on 2025-01-05
  (`congestion_pricing_start_date` in `dbt/dbt_project.yml`), so January 2025 contains
  four days without the fee. `dim_date.is_congestion_pricing_active` marks the exact days.
- **Before/after comparisons** around congestion pricing are descriptive only. They
  are not causal: seasonality, fare changes and other events in the same period are
  not controlled for.
- **Payment type 0** ("flex fare"; 8.9% of rows in 2024-12, 15.5% in 2025-01) has NULL passenger count,
  rate code, airport fee and congestion surcharge. These trips count toward trips and
  revenue but never toward tip rate.
