-- Trips that break at least one staging rule, with the first rule broken.

select *
from {{ ref('stg_yellow_trips_classified') }}
where reject_reason is not null
