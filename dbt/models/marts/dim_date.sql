-- One row per calendar day from the first to the last valid pickup date.

with bounds as (
    select
        cast(min(pickup_at) as date) as first_day,
        cast(max(pickup_at) as date) as last_day
    from {{ ref('stg_yellow_trips') }}
),

days as (
    select cast(day as date) as date_day
    from bounds, generate_series(first_day, last_day, interval 1 day) as t(day)
)

select
    cast(date_day as date) as date_day,
    cast(date_trunc('month', date_day) as date) as month_start,
    cast(strftime(date_day, '%Y-%m') as varchar) as year_month,
    cast(year(date_day) as integer) as year,
    cast(month(date_day) as integer) as month,
    cast(isodow(date_day) as integer) as day_of_week,
    cast(dayname(date_day) as varchar) as day_name,
    cast(isodow(date_day) in (6, 7) as boolean) as is_weekend,
    cast(
        date_day >= date '{{ var("congestion_pricing_start_date") }}' as boolean
    ) as is_congestion_pricing_active
from days
