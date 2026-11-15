-- Fact grain: (snapshot_date, unit_id) must be unique.

select
    snapshot_date,
    unit_id,
    count(*) as row_count
from {{ ref('fct_mastr_units') }}
group by snapshot_date, unit_id
having count(*) > 1
