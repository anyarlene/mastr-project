-- Where Raw has a non-blank numeric string, Staging must parse it successfully.

with raw_all as (

    select *
    from {{ source('mastr_raw', 'raw_mastr_wind') }}
    union all
    select *
    from {{ source('mastr_raw', 'raw_mastr_solar') }}
    union all
    select *
    from {{ source('mastr_raw', 'raw_mastr_biomass') }}
    union all
    select *
    from {{ source('mastr_raw', 'raw_mastr_storage') }}

),

staging_all as (

    select * from {{ ref('stg_mastr_wind') }}
    union all
    select * from {{ ref('stg_mastr_solar') }}
    union all
    select * from {{ ref('stg_mastr_biomass') }}
    union all
    select * from {{ ref('stg_mastr_storage') }}

)

select
    s.snapshot_date,
    s.unit_id,
    'net_power_kw' as field_name,
    r.nettonennleistung_der_einheit as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.nettonennleistung_der_einheit), '') is not null
    and s.net_power_kw is null

union all

select
    s.snapshot_date,
    s.unit_id,
    'gross_power_kw' as field_name,
    r.bruttoleistung_der_einheit as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.bruttoleistung_der_einheit), '') is not null
    and s.gross_power_kw is null

union all

select
    s.snapshot_date,
    s.unit_id,
    'storage_capacity_kwh' as field_name,
    r.nutzbare_speicherkapazitaet_in_kwh as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.nutzbare_speicherkapazitaet_in_kwh), '') is not null
    and s.storage_capacity_kwh is null
