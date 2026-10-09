---
title: Fare and tip trends
---

How do average fare per mile and tip rate evolve month by month?

```sql monthly
select
    month_start,
    year_month,
    strftime(month_start, '%b %y') as month_label,
    trips,
    fare_per_mile_usd,
    tip_rate,
    credit_card_trips
from taxi.fct_monthly_metrics
order by month_start
```

```sql window
select min(year_month) as first_month, max(year_month) as last_month
from taxi.fct_monthly_metrics
```

Valid trips only.

**Data window:** <Value data={window} column=first_month /> to <Value data={window} column=last_month />

<LineChart data={monthly} x=month_label y=fare_per_mile_usd sort=false title="Fare per mile (USD)" yFmt=usd2 />

<LineChart data={monthly} x=month_label y=tip_rate sort=false title="Tip rate (credit-card trips)" yFmt=pct1 />

<DataTable data={monthly} rows=all>
    <Column id=year_month title="Month" />
    <Column id=trips fmt=num0 />
    <Column id=fare_per_mile_usd title="Fare per mile (USD)" fmt=usd2 />
    <Column id=credit_card_trips title="Credit-card trips" fmt=num0 />
    <Column id=tip_rate title="Tip rate" fmt=pct1 />
</DataTable>

## Definitions and caveats

- **Fare per mile** = `sum(fare_amount) / sum(trip_distance)` over trips with distance above zero.
  Zero-distance trips are valid trips but have no meaningful per-mile price, so they are excluded here.
- **Tip rate** = `sum(tip_amount) / sum(fare_amount)` over **credit-card trips with a positive fare**.
  Cash tips are not recorded, so cash trips are left out rather than counted as zero tips.
- Both are **ratios of sums**: long trips weigh more, and short trips with extreme per-trip ratios
  do not distort the figure.
- A window of at most 12 months cannot separate a trend from seasonality, so small month-to-month moves are not evidence of a trend.
