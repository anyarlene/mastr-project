{{ config(materialized='table') }}

select
    i.snapshot_date,
    i.unit_id,
    i.municipality_id,
    e.energy_source_id,
    s.status_id,
    i.unit_name,
    i.storage_id,
    i.is_operational,
    i.generation_power_kw,
    i.storage_power_kw,
    i.storage_capacity_kwh,
    i.gross_power_kw,
    i.commissioning_date,
    i.planned_commissioning_date,
    i.decommissioned_date,
    i.last_updated_at,
    i.source_file,
    i.ingested_at
from {{ ref('int_mastr_units') }} as i
inner join {{ ref('dim_energy_source') }} as e
    on i.energy_source_code = e.energy_source_code
inner join {{ ref('dim_status') }} as s
    on i.status_code = s.status_code
inner join {{ ref('dim_municipality') }} as m
    on i.municipality_id = m.municipality_id
