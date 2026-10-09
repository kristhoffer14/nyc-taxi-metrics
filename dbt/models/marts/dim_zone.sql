select
    cast(location_id as integer) as location_id,
    cast(borough as varchar) as borough,
    cast(zone_name as varchar) as zone_name,
    cast(service_zone as varchar) as service_zone,
    cast(borough = 'Manhattan' as boolean) as is_manhattan
from {{ ref('stg_taxi_zones') }}
