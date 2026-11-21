-- Materialized CDC fact must not contain UNCHANGED rows.

select
    from_snapshot_date,
    to_snapshot_date,
    unit_id,
    change_type
from {{ ref('fct_mastr_unit_changes') }}
where change_type not in ('INSERT', 'UPDATE', 'DELETE_CANDIDATE')
