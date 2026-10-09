-- Every raw trip, typed and renamed, with the first reject rule it breaks.
-- stg_yellow_trips and stg_yellow_trips_rejected split this view on
-- reject_reason, so together they always contain every raw row exactly once.

with trips as (

    select
        source_month || '-' || lpad(cast(source_row as varchar), 8, '0') as trip_id,
        source_month,
        source_file,
        source_row,
        vendorid as vendor_id,
        tpep_pickup_datetime as pickup_at,
        tpep_dropoff_datetime as dropoff_at,
        passenger_count,
        trip_distance as trip_distance_miles,
        ratecodeid as rate_code_id,
        store_and_fwd_flag,
        pulocationid as pickup_location_id,
        dolocationid as dropoff_location_id,
        cast(payment_type as integer) as payment_type,
        fare_amount,
        extra as extra_amount,
        mta_tax as mta_tax_amount,
        tip_amount,
        tolls_amount,
        improvement_surcharge as improvement_surcharge_amount,
        total_amount,
        congestion_surcharge as congestion_surcharge_amount,
        airport_fee as airport_fee_amount,
        cbd_congestion_fee as cbd_congestion_fee_amount
    from {{ source('raw', 'yellow_trips') }}

),

zones as (

    select location_id from {{ ref('stg_taxi_zones') }}

)

select
    trips.*,
    case
        when trips.pickup_at is null
            or trips.dropoff_at is null
            or trips.fare_amount is null
            or trips.total_amount is null
            or trips.trip_distance_miles is null
            then 'missing_required_value'
        when trips.fare_amount < 0 or trips.total_amount < 0
            then 'negative_amount'
        when trips.dropoff_at <= trips.pickup_at
            then 'non_positive_duration'
        when trips.dropoff_at
            > trips.pickup_at + to_hours({{ var('max_trip_duration_hours') }})
            then 'excessive_duration'
        when strftime(trips.pickup_at, '%Y-%m') <> trips.source_month
            then 'pickup_outside_source_month'
        when trips.trip_distance_miles < 0
            or trips.trip_distance_miles > {{ var('max_trip_distance_miles') }}
            then 'invalid_distance'
        when pickup_zone.location_id is null or dropoff_zone.location_id is null
            then 'unknown_zone'
    end as reject_reason
from trips
left join zones as pickup_zone
    on trips.pickup_location_id = pickup_zone.location_id
left join zones as dropoff_zone
    on trips.dropoff_location_id = dropoff_zone.location_id
