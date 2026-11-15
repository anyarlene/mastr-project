{{ config(materialized='table') }}

select
    energy_source_id,
    energy_source_code,
    energy_source_label,
    energy_source_group
from {{ ref('seed_energy_sources') }}
