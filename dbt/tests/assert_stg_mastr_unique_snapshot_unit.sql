-- Composite uniqueness across the four Staging views: (snapshot_date, unit_id).
-- Fails if any duplicate pairs exist within or across Staging.

with staging_all as (

    select snapshot_date, unit_id from {{ ref('stg_mastr_wind') }}
    union all
    select snapshot_date, unit_id from {{ ref('stg_mastr_solar') }}
    union all
    select snapshot_date, unit_id from {{ ref('stg_mastr_biomass') }}
    union all
    select snapshot_date, unit_id from {{ ref('stg_mastr_storage') }}

)

select
    snapshot_date,
    unit_id,
    count(*) as row_count
from staging_all
group by snapshot_date, unit_id
having count(*) > 1
