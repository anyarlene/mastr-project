-- Composite uniqueness: (snapshot_date, unit_id) must be unique.
-- Fails if any duplicate pairs exist.

select
    snapshot_date,
    unit_id,
    count(*) as row_count
from {{ ref('stg_mastr_units') }}
group by snapshot_date, unit_id
having count(*) > 1
