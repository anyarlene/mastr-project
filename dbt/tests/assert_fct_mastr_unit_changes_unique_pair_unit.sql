-- Grain (from_snapshot_date, to_snapshot_date, unit_id) must be unique.

select
    from_snapshot_date,
    to_snapshot_date,
    unit_id,
    count(*) as row_count
from {{ ref('fct_mastr_unit_changes') }}
group by from_snapshot_date, to_snapshot_date, unit_id
having count(*) > 1
