-- Fails (returns rows) if fct_demand_hourly has more than one row for a grain key.

select
    year_month,
    day_of_week,
    pickup_hour,
    pickup_borough,
    count(*) as row_count
from {{ ref('fct_demand_hourly') }}
group by 1, 2, 3, 4
having count(*) > 1
