-- CDC pairs must never use the legacy mixed-filter snapshot 2026-11-09.

select
    from_snapshot_date,
    to_snapshot_date,
    unit_id,
    change_type
from {{ ref('int_mastr_unit_cdc') }}
where from_snapshot_date = date '2026-11-09'
   or to_snapshot_date = date '2026-11-09'
