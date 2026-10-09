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

Valid trips only. Tolling began on **2025-01-05**; the daily charts use that exact date.

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

<DataTable data={monthly_share} rows=all>
    <Column id=year_month title="Month" />
    <Column id=share_label title="Trips with CBD fee" align=right />
</DataTable>

The share is **n/a before tolling**: the fee did not exist, and the TLC files before 2025 have no such column.

```sql daily
select
    strftime(date_day, '%Y-%m-%d') as day,
    trips,
    cbd_fee_trip_share,
    manhattan_pickup_trips,
    manhattan_pickup_avg_fare_usd
from taxi.fct_daily_congestion
order by day
```

<LineChart data={daily} x=day xType=category sort=false y=cbd_fee_trip_share title="Daily share of trips with the CBD fee" yFmt=pct1>
    <ReferenceLine x="2025-01-05" label="Tolling starts 2025-01-05" hideValue=true />
</LineChart>

## Manhattan pickups before and after

```sql before_after
select
    case when is_congestion_pricing_month then 'After' else 'Before' end as period,
    min(year_month) || ' to ' || max(year_month) as months_covered,
    count(*) as months,
    sum(manhattan_pickup_trips) / count(*) as avg_monthly_manhattan_trips,
    sum(manhattan_pickup_avg_fare_usd * manhattan_pickup_trips) / sum(manhattan_pickup_trips) as avg_fare_usd
from taxi.fct_monthly_metrics
group by is_congestion_pricing_month
order by is_congestion_pricing_month
```

<DataTable data={before_after}>
    <Column id=period title="Period" />
    <Column id=months_covered title="Months covered" />
    <Column id=months title="Months" fmt=num0 />
    <Column id=avg_monthly_manhattan_trips title="Manhattan pickups per month" fmt=num0 />
    <Column id=avg_fare_usd title="Average fare (USD)" fmt=usd2 />
</DataTable>

The table works by month, so **2025-01 counts as an "After" month although its first four days
(2025-01-01 to 2025-01-04) were before tolling began**. Those four days carry no fee and are mixed
into the "After" figures; the daily charts below use the exact date.

<LineChart data={daily} x=day xType=category sort=false y=manhattan_pickup_trips title="Daily Manhattan pickups" yFmt=num0>
    <ReferenceLine x="2025-01-05" label="Tolling starts 2025-01-05" hideValue=true />
</LineChart>

<LineChart data={daily} x=day xType=category sort=false y=manhattan_pickup_avg_fare_usd title="Daily average fare, Manhattan pickups (USD)" yFmt=usd2>
    <ReferenceLine x="2025-01-05" label="Tolling starts 2025-01-05" hideValue=true />
</LineChart>

## Caveats

- Average fare is `fare_amount` (meter fare), which excludes the congestion fee itself, tolls, taxes and tips.
- "Before" and "After" cover different months of the year, so seasonal demand differences are mixed in.
- Short windows and a handful of months give very little to compare. Treat differences as a description of this data, not an effect estimate.
- The zone covers local streets and avenues in Manhattan south of and including 60th Street, excluding the FDR Drive, West Side Highway/Route 9A and the Hugh L. Carey Tunnel connections to West Street. Taxis pay a $0.75 per-trip charge on trips to, from, within or through the zone, so not every Manhattan pickup carries the fee. Source: MTA, [Congestion Relief Zone](https://www.mta.info/agency/bridges-and-tunnels/congestion-relief-zone) and [frequently asked questions](https://www.mta.info/fares-tolls/tolls/congestion-relief-zone/faq).

---

Data: [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
