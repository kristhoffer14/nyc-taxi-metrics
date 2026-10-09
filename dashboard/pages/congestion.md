---
title: Congestion fee
---

After NYC congestion pricing started, what share of trips carry the congestion relief
zone fee (`cbd_congestion_fee`), and how did Manhattan-pickup trips and fares change
compared with the months before?

<Alert status=warning>
This view is <b>descriptive, not causal</b>. Seasonality, fare changes, weather and other events
in the same period are not controlled for, so a difference before and after tolling began
cannot be attributed to congestion pricing.
</Alert>

```sql window
select min(year_month) as first_month, max(year_month) as last_month
from taxi.fct_monthly_metrics
```

Valid trips only. Tolling began on **2025-01-05**. Monthly views treat 2025-01 as the first "after" month
(it includes four days without the fee); daily views use the exact date.

**Data window:** <Value data={window} column=first_month /> to <Value data={window} column=last_month />

## Share of trips with the congestion fee

```sql monthly_share
select
    month_start,
    year_month,
    cbd_fee_trip_share,
    coalesce(printf('%.1f%%', cbd_fee_trip_share * 100), 'n/a') as share_label
from taxi.fct_monthly_metrics
order by month_start
```

<DataTable data={monthly_share}>
    <Column id=year_month title="Month" />
    <Column id=share_label title="Trips with CBD fee" align=right />
</DataTable>

The share is **n/a before tolling**: the fee did not exist, and the TLC files before 2025 have no such column.

```sql daily
select
    date_day,
    trips,
    cbd_fee_trip_share,
    manhattan_pickup_trips,
    manhattan_pickup_avg_fare_usd
from taxi.fct_daily_congestion
order by date_day
```

<LineChart data={daily} x=date_day y=cbd_fee_trip_share title="Daily share of trips with the CBD fee" yFmt=pct1 xFmt="d mmm yyyy">
    <ReferenceLine x="2025-01-05" label="Tolling starts 2025-01-05" hideValue=true />
</LineChart>

## Manhattan pickups before and after

```sql before_after
select
    case when is_congestion_pricing_month then 'After (from ' || year_month || ')' else 'Before' end as period,
    is_congestion_pricing_month,
    count(*) as months,
    sum(manhattan_pickup_trips) / count(*) as avg_monthly_manhattan_trips,
    sum(manhattan_pickup_avg_fare_usd * manhattan_pickup_trips) / sum(manhattan_pickup_trips) as avg_fare_usd
from taxi.fct_monthly_metrics
group by is_congestion_pricing_month, case when is_congestion_pricing_month then 'After (from ' || year_month || ')' else 'Before' end
order by is_congestion_pricing_month
```

<DataTable data={before_after}>
    <Column id=period title="Period" />
    <Column id=months title="Months" fmt=num0 />
    <Column id=avg_monthly_manhattan_trips title="Manhattan pickups per month" fmt=num0 />
    <Column id=avg_fare_usd title="Average fare (USD)" fmt=usd2 />
</DataTable>

<LineChart data={daily} x=date_day y=manhattan_pickup_trips title="Daily Manhattan pickups" yFmt=num0 xFmt="d mmm yyyy">
    <ReferenceLine x="2025-01-05" label="Tolling starts 2025-01-05" hideValue=true />
</LineChart>

<LineChart data={daily} x=date_day y=manhattan_pickup_avg_fare_usd title="Daily average fare, Manhattan pickups (USD)" yFmt=usd2 xFmt="d mmm yyyy">
    <ReferenceLine x="2025-01-05" label="Tolling starts 2025-01-05" hideValue=true />
</LineChart>

## Caveats

- Average fare is `fare_amount` (meter fare), which excludes the congestion fee itself, tolls, taxes and tips.
- "Before" and "After" cover different months of the year, so seasonal demand differences are mixed in.
- Short windows and a handful of months give very little to compare. Treat differences as a description of this data, not an effect estimate.
- The congestion relief zone fee applies to trips entering or in the zone below 60th Street in Manhattan, not to every Manhattan pickup.
