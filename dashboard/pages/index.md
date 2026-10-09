---
title: NYC yellow taxi metrics
---

Tested metrics on NYC TLC yellow taxi trips, prepared for the Head of Mobility Analytics.
Every figure comes from a dbt mart over **valid trips** only; rejected trips (negative
fares, dropoff before pickup, pickup outside the file's month) are excluded.

```sql overview
select
    min(year_month) as first_month,
    max(year_month) as last_month,
    count(*) as months,
    sum(trips) as trips,
    sum(revenue_usd) as revenue_usd
from taxi.fct_monthly_metrics
```

<BigValue data={overview} value=trips title="Valid trips" fmt=num0 />
<BigValue data={overview} value=revenue_usd title="Revenue (USD)" fmt=usd0 />
<BigValue data={overview} value=months title="Months" fmt=num0 />

**Data window:** <Value data={overview} column=first_month /> to <Value data={overview} column=last_month />

## Pages

1. [Demand patterns](/demand): trips and revenue by hour, weekday and pickup borough.
2. [Fare and tip trends](/fares): fare per mile and tip rate, month by month.
3. [Congestion fee](/congestion): share of trips with the congestion fee, and Manhattan pickups and fares before and after tolling began on 2025-01-05.

## Reading the numbers

- **Revenue** is the sum of `total_amount`: everything charged to the rider, including
  card tips but not cash tips (the TLC does not record them).
- Ratio metrics (fare per mile, tip rate) are **ratios of sums**, not averages of per-trip ratios.
- Full definitions: `docs/metrics.md` in the repository.

---

Data: [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
