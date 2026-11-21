-- Intermediate row count must match the four Staging views combined.

with staging_all as (

    select unit_id from {{ ref('stg_mastr_wind') }}
    union all
    select unit_id from {{ ref('stg_mastr_solar') }}
    union all
    select unit_id from {{ ref('stg_mastr_biomass') }}
    union all
    select unit_id from {{ ref('stg_mastr_storage') }}

)

select
    staging_counts.row_count as staging_row_count,
    intermediate_counts.row_count as intermediate_row_count
from (
    select count(*) as row_count
    from staging_all
) as staging_counts
cross join (
    select count(*) as row_count
    from {{ ref('int_mastr_units') }}
) as intermediate_counts
where staging_counts.row_count != intermediate_counts.row_count
