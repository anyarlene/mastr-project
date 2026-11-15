{{ config(severity='warn') }}

-- Warn when unrecognized energy carriers produce unknown classifications.
-- Does not fail the pipeline; expected count for snapshot 2026-11-09 is zero.

select
    snapshot_date,
    unit_id,
    energy_carrier_code,
    storage_technology_code,
    energy_source_code,
    energy_source_group,
    source_file
from {{ ref('int_mastr_units') }}
where energy_source_code = 'unknown'
   or energy_source_group = 'unknown'
