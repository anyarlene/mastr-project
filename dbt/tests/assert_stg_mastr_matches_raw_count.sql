-- Source-to-staging row count consistency across the four Raw / Staging tables.

with raw_all as (

    select snapshot_date, mastr_nr_der_einheit
    from {{ source('mastr_raw', 'raw_mastr_wind') }}
    union all
    select snapshot_date, mastr_nr_der_einheit
    from {{ source('mastr_raw', 'raw_mastr_solar') }}
    union all
    select snapshot_date, mastr_nr_der_einheit
    from {{ source('mastr_raw', 'raw_mastr_biomass') }}
    union all
    select snapshot_date, mastr_nr_der_einheit
    from {{ source('mastr_raw', 'raw_mastr_storage') }}

),

staging_all as (

    select unit_id from {{ ref('stg_mastr_wind') }}
    union all
    select unit_id from {{ ref('stg_mastr_solar') }}
    union all
    select unit_id from {{ ref('stg_mastr_biomass') }}
    union all
    select unit_id from {{ ref('stg_mastr_storage') }}

)

select
    raw_counts.row_count as raw_row_count,
    stg_counts.row_count as staging_row_count
from (
    select count(*) as row_count from raw_all
) as raw_counts
cross join (
    select count(*) as row_count from staging_all
) as stg_counts
where raw_counts.row_count != stg_counts.row_count
