-- One row per month of valid trips. Ratio metrics are ratios of sums.
-- Definitions are in docs/metrics.md.

with trips as (
    select
        trips.*,
        zones.is_manhattan as is_manhattan_pickup
    from {{ ref('fct_trips') }} as trips
    inner join {{ ref('dim_zone') }} as zones
        on trips.pickup_location_id = zones.location_id
),

monthly as (
    select
        source_month as year_month,
        count(*) as trips,
        sum(total_amount) as revenue_usd,
        sum(fare_amount) filter (where trip_distance_miles > 0) as fare_on_distance_trips,
        sum(trip_distance_miles) filter (where trip_distance_miles > 0) as miles_on_distance_trips,
        count(*) filter (where is_credit_card and fare_amount > 0) as credit_card_trips,
        sum(tip_amount) filter (where is_credit_card and fare_amount > 0) as credit_card_tips,
        sum(fare_amount) filter (where is_credit_card and fare_amount > 0) as credit_card_fares,
        count(*) filter (where has_cbd_fee) as cbd_fee_trips,
        count(*) filter (where is_manhattan_pickup) as manhattan_pickup_trips,
        sum(fare_amount) filter (where is_manhattan_pickup) as manhattan_pickup_fares
    from trips
    group by source_month
)

select
    cast(year_month as varchar) as year_month,
    cast(strptime(year_month, '%Y-%m') as date) as month_start,
    cast(trips as bigint) as trips,
    cast(revenue_usd as double) as revenue_usd,
    cast(fare_on_distance_trips / nullif(miles_on_distance_trips, 0) as double) as fare_per_mile_usd,
    cast(credit_card_trips as bigint) as credit_card_trips,
    cast(credit_card_tips / nullif(credit_card_fares, 0) as double) as tip_rate,
    cast(
        year_month >= strftime(date '{{ var("congestion_pricing_start_date") }}', '%Y-%m')
        as boolean
    ) as is_congestion_pricing_month,
    cast(
        case
            when year_month >= strftime(date '{{ var("congestion_pricing_start_date") }}', '%Y-%m')
                then cbd_fee_trips / trips
        end as double
    ) as cbd_fee_trip_share,
    cast(manhattan_pickup_trips as bigint) as manhattan_pickup_trips,
    cast(manhattan_pickup_fares / nullif(manhattan_pickup_trips, 0) as double)
        as manhattan_pickup_avg_fare_usd
from monthly
