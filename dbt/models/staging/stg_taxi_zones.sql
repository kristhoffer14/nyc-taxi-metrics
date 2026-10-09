select
    cast(LocationID as integer) as location_id,
    Borough as borough,
    Zone as zone_name,
    service_zone
from {{ source('raw', 'taxi_zones') }}
