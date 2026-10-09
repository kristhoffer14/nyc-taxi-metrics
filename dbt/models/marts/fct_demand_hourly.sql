-- Demand by month, ISO weekday, pickup hour and pickup borough.
-- Definitions are in docs/metrics.md.

select
    cast(trips.source_month as varchar) as year_month,
    cast(isodow(trips.pickup_date) as integer) as day_of_week,
    cast(trips.pickup_hour as integer) as pickup_hour,
    cast(zones.borough as varchar) as pickup_borough,
    cast(count(*) as bigint) as trips,
    cast(sum(trips.total_amount) as double) as revenue_usd
from {{ ref('fct_trips') }} as trips
inner join {{ ref('dim_zone') }} as zones
    on trips.pickup_location_id = zones.location_id
group by 1, 2, 3, 4
