-- Staleness check: for every source month, fct_trips must hold exactly the trips
-- that stg_yellow_trips currently produces. Catches an incremental fct_trips that
-- was built under older staging rules. Returns the months that differ; the test
-- passes when it returns none.

with staging_counts as (
    select source_month, count(*) as staging_rows
    from {{ ref('stg_yellow_trips') }}
    group by source_month
),

fact_counts as (
    select source_month, count(*) as fact_rows
    from {{ ref('fct_trips') }}
    group by source_month
)

select
    coalesce(s.source_month, f.source_month) as source_month,
    coalesce(s.staging_rows, 0) as staging_rows,
    coalesce(f.fact_rows, 0) as fact_rows
from staging_counts as s
full outer join fact_counts as f on s.source_month = f.source_month
where coalesce(s.staging_rows, 0) <> coalesce(f.fact_rows, 0)
