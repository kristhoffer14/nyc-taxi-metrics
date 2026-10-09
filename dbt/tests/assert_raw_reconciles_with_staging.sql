-- Reconciliation: for every source month, raw rows = valid rows + rejected rows.
-- Returns the months that do not reconcile; the test passes when it returns none.

with raw_counts as (
    select source_month, count(*) as raw_rows
    from {{ source('raw', 'yellow_trips') }}
    group by source_month
),

valid_counts as (
    select source_month, count(*) as valid_rows
    from {{ ref('stg_yellow_trips') }}
    group by source_month
),

rejected_counts as (
    select source_month, count(*) as rejected_rows
    from {{ ref('stg_yellow_trips_rejected') }}
    group by source_month
)

select
    coalesce(r.source_month, v.source_month, j.source_month) as source_month,
    coalesce(r.raw_rows, 0) as raw_rows,
    coalesce(v.valid_rows, 0) as valid_rows,
    coalesce(j.rejected_rows, 0) as rejected_rows
from raw_counts as r
full outer join valid_counts as v on r.source_month = v.source_month
full outer join rejected_counts as j on coalesce(r.source_month, v.source_month) = j.source_month
where coalesce(r.raw_rows, 0) <> coalesce(v.valid_rows, 0) + coalesce(j.rejected_rows, 0)
