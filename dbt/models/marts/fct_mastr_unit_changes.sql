{{ config(materialized='table') }}

/*
  Materialized CDC change events for BI / QA.

  Excludes UNCHANGED rows. DELETE_CANDIDATE means the unit was present in the
  earlier eligible snapshot and absent in the later one — treat as a candidate,
  not a confirmed physical deletion.
*/

select
    from_snapshot_date,
    to_snapshot_date,
    unit_id,
    source_file,
    change_type,
    before_status_code,
    after_status_code,
    before_net_power_kw,
    after_net_power_kw,
    before_storage_capacity_kwh,
    after_storage_capacity_kwh,
    before_municipality_id,
    after_municipality_id
from {{ ref('int_mastr_unit_cdc') }}
where change_type in ('INSERT', 'UPDATE', 'DELETE_CANDIDATE')
