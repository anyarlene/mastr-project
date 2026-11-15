-- Where Raw has a non-blank date string, Staging must parse it successfully.

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
    'commissioning_date' as field_name,
    r.inbetriebnahmedatum_der_einheit as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.inbetriebnahmedatum_der_einheit), '') is not null
    and s.commissioning_date is null

union all

select
    s.snapshot_date,
    s.unit_id,
    'registration_date' as field_name,
    r.registrierungsdatum_der_einheit as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.registrierungsdatum_der_einheit), '') is not null
    and s.registration_date is null

union all

select
    s.snapshot_date,
    s.unit_id,
    'last_updated_at' as field_name,
    r.letzte_aktualisierung as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.letzte_aktualisierung), '') is not null
    and s.last_updated_at is null

union all

select
    s.snapshot_date,
    s.unit_id,
    'planned_commissioning_date' as field_name,
    r.datum_der_geplanten_inbetriebnahme as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.datum_der_geplanten_inbetriebnahme), '') is not null
    and s.planned_commissioning_date is null

union all

select
    s.snapshot_date,
    s.unit_id,
    'decommissioned_date' as field_name,
    r.datum_der_endgueltigen_stilllegung as source_value
from staging_all as s
inner join raw_all as r
    on s.unit_id = r.mastr_nr_der_einheit
    and s.snapshot_date = r.snapshot_date
where nullif(trim(r.datum_der_endgueltigen_stilllegung), '') is not null
    and s.decommissioned_date is null
