-- Trips that pass every staging rule. See stg_yellow_trips_classified.

select * exclude (reject_reason)
from {{ ref('stg_yellow_trips_classified') }}
where reject_reason is null
