-- One row per pickup day: trips, CBD fee share and Manhattan pickups.
-- Daily views use the exact congestion pricing start date (SCR-2).
-- Definitions are in docs/metrics.md.

with trips as (
    select
        trips.pickup_date,
        trips.has_cbd_fee,
        trips.fare_amount,
        zones.is_manhattan as is_manhattan_pickup
    from {{ ref('fct_trips') }} as trips
    inner join {{ ref('dim_zone') }} as zones
        on trips.pickup_location_id = zones.location_id
),

daily as (
    select
        pickup_date,
        count(*) as trips,
        count(*) filter (where has_cbd_fee) as cbd_fee_trips,
        count(*) filter (where is_manhattan_pickup) as manhattan_pickup_trips,
        sum(fare_amount) filter (where is_manhattan_pickup) as manhattan_pickup_fares
    from trips
    group by pickup_date
)

select
    cast(daily.pickup_date as date) as date_day,
    cast(dates.is_congestion_pricing_active as boolean) as is_congestion_pricing_active,
    cast(daily.trips as bigint) as trips,
    cast(
        case when dates.is_congestion_pricing_active then daily.cbd_fee_trips / daily.trips end
        as double
    ) as cbd_fee_trip_share,
    cast(daily.manhattan_pickup_trips as bigint) as manhattan_pickup_trips,
    cast(daily.manhattan_pickup_fares / nullif(daily.manhattan_pickup_trips, 0) as double)
        as manhattan_pickup_avg_fare_usd
from daily
inner join {{ ref('dim_date') }} as dates
    on daily.pickup_date = dates.date_day
