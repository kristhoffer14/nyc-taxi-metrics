---
title: Demand patterns
---

How do trips and revenue vary by hour of day, weekday and pickup borough?

```sql window
select min(year_month) as first_month, max(year_month) as last_month
from taxi.fct_demand_hourly
```

Valid trips only. Filters apply to the hour and weekday charts; the borough charts always show all boroughs.

**Data window:** <Value data={window} column=first_month /> to <Value data={window} column=last_month />

```sql boroughs
select 'All boroughs' as label, '%' as value, 0 as sort_order
union all
select distinct pickup_borough, pickup_borough, 1 from taxi.fct_demand_hourly
order by sort_order, label
```

<Dropdown name=borough data={boroughs} value=value label=label defaultValue="%" title="Pickup borough" />

## By hour of day

```sql by_hour
select
    pickup_hour,
    printf('%02d', cast(pickup_hour as integer)) as hour_label,
    sum(trips) as trips,
    sum(revenue_usd) as revenue_usd
from taxi.fct_demand_hourly
where pickup_borough like '${inputs.borough.value}'
group by pickup_hour
order by pickup_hour
```

<LineChart data={by_hour} x=hour_label xType=category sort=false y=trips title="Trips by pickup hour" xAxisTitle="Hour of day" yFmt=num0 />

<LineChart data={by_hour} x=hour_label xType=category sort=false y=revenue_usd title="Revenue by pickup hour (USD)" xAxisTitle="Hour of day" yFmt=usd0 />

## By weekday

```sql by_weekday
select
    day_of_week,
    case day_of_week
        when 1 then 'Mon' when 2 then 'Tue' when 3 then 'Wed' when 4 then 'Thu'
        when 5 then 'Fri' when 6 then 'Sat' else 'Sun'
    end as weekday,
    sum(trips) as trips,
    sum(revenue_usd) as revenue_usd
from taxi.fct_demand_hourly
where pickup_borough like '${inputs.borough.value}'
group by day_of_week
order by day_of_week
```

<Grid cols=2>
    <BarChart data={by_weekday} x=weekday y=trips title="Trips by weekday" sort=false yFmt=num0 />
    <BarChart data={by_weekday} x=weekday y=revenue_usd title="Revenue by weekday (USD)" sort=false yFmt=usd0 />
</Grid>

## By pickup borough

```sql by_borough
select
    pickup_borough,
    sum(trips) as trips,
    sum(revenue_usd) as revenue_usd
from taxi.fct_demand_hourly
group by pickup_borough
order by trips desc
```

<Grid cols=2>
    <BarChart data={by_borough} x=pickup_borough y=trips title="Trips by pickup borough (millions)" swapXY=true yFmt=num0m />
    <BarChart data={by_borough} x=pickup_borough y=revenue_usd title="Revenue by pickup borough (millions of USD)" swapXY=true yFmt=usd0m />
</Grid>

<DataTable data={by_borough} rows=all>
    <Column id=pickup_borough title="Pickup borough" />
    <Column id=trips fmt=num0 />
    <Column id=revenue_usd title="Revenue (USD)" fmt=usd0 />
</DataTable>

## Caveats

- Hours are local time at the pickup. Weekday is the ISO weekday of the pickup date.
- Revenue excludes cash tips, which the TLC does not record.
- Boroughs `EWR`, `Unknown` and `N/A` are TLC zone categories, kept as their own values.
- A window that spans several months sums them; seasonality is not adjusted.
