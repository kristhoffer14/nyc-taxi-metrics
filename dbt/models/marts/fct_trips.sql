{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='source_month',
        on_schema_change='fail'
    )
}}

-- One row per valid trip. Incremental by source month: a run processes only
-- months that are new or whose load_log.loaded_at changed (a --force reload)
-- and replaces them whole. Comparing loaded_at for equality, not "newer than",
-- avoids depending on clocks or time zones.

with months_to_process as (
    select load_log.source_month, load_log.loaded_at
    from {{ source('raw', 'load_log') }} as load_log
    {% if is_incremental() %}
    where not exists (
        select 1
        from (select distinct source_month, loaded_at from {{ this }}) as built
        where built.source_month = load_log.source_month
            and built.loaded_at = load_log.loaded_at
    )
    {% endif %}
),

trips as (
    select
        trips.*,
        months_to_process.loaded_at
    from {{ ref('stg_yellow_trips') }} as trips
    inner join months_to_process
        on trips.source_month = months_to_process.source_month
)

select
    cast(trip_id as varchar) as trip_id,
    cast(source_month as varchar) as source_month,
    cast(pickup_at as date) as pickup_date,
    cast(pickup_at as timestamp) as pickup_at,
    cast(dropoff_at as timestamp) as dropoff_at,
    cast(hour(pickup_at) as integer) as pickup_hour,
    cast(vendor_id as integer) as vendor_id,
    cast(pickup_location_id as integer) as pickup_location_id,
    cast(dropoff_location_id as integer) as dropoff_location_id,
    cast(payment_type as integer) as payment_type,
    cast(
        case payment_type
            when 0 then 'Flex fare'
            when 1 then 'Credit card'
            when 2 then 'Cash'
            when 3 then 'No charge'
            when 4 then 'Dispute'
            when 5 then 'Unknown'
            when 6 then 'Voided'
        end as varchar
    ) as payment_type_name,
    cast(payment_type = 1 as boolean) as is_credit_card,
    cast(passenger_count as bigint) as passenger_count,
    cast(trip_distance_miles as double) as trip_distance_miles,
    cast(date_diff('second', pickup_at, dropoff_at) / 60.0 as double) as trip_duration_minutes,
    cast(fare_amount as double) as fare_amount,
    cast(tip_amount as double) as tip_amount,
    cast(tolls_amount as double) as tolls_amount,
    cast(total_amount as double) as total_amount,
    cast(cbd_congestion_fee_amount as double) as cbd_congestion_fee_amount,
    cast(coalesce(cbd_congestion_fee_amount > 0, false) as boolean) as has_cbd_fee,
    cast(loaded_at as timestamp) as loaded_at
from trips
