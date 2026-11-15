-- is_operational must equal (status_code = 'operational').

select
    snapshot_date,
    unit_id,
    status_code,
    is_operational
from {{ ref('int_mastr_units') }}
where is_operational != (status_code = 'operational')
   or is_operational is null
