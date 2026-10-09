-- Fails (returns rows) if the dashboard marts disagree with fct_monthly_metrics
-- on trips or Manhattan pickups for any month.

with monthly as (
    select year_month, trips, manhattan_pickup_trips
    from {{ ref('fct_monthly_metrics') }}
),

demand as (
    select
        year_month,
        sum(trips) as trips,
        sum(trips) filter (where pickup_borough = 'Manhattan') as manhattan_pickup_trips
    from {{ ref('fct_demand_hourly') }}
    group by year_month
),

daily as (
    select
        strftime(date_day, '%Y-%m') as year_month,
        sum(trips) as trips,
        sum(manhattan_pickup_trips) as manhattan_pickup_trips
    from {{ ref('fct_daily_congestion') }}
    group by 1
)

select
    monthly.year_month,
    monthly.trips as monthly_trips,
    demand.trips as demand_trips,
    daily.trips as daily_trips
from monthly
left join demand on monthly.year_month = demand.year_month
left join daily on monthly.year_month = daily.year_month
where demand.trips is distinct from monthly.trips
    or daily.trips is distinct from monthly.trips
    or coalesce(demand.manhattan_pickup_trips, 0) != monthly.manhattan_pickup_trips
    or coalesce(daily.manhattan_pickup_trips, 0) != monthly.manhattan_pickup_trips
