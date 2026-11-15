{{ config(materialized='view') }}

/*
  Staging (Silver): English renames, type casts, status/energy-carrier codes.

  German→English categorical mappings are isolated here.
  Downstream models must use English column names and codes only.

  Deferred to Intermediate:
    - is_operational
    - energy_source_code / energy_source_group
    - generation_power_kw / storage_power_kw measure split
*/

with source as (

    select * from {{ source('mastr_raw', 'raw_mastr_units') }}

),

renamed as (

    select
        -- identifiers
        mastr_nr_der_einheit as unit_id,
        nullif(trim(mastr_nr_der_speichereinheit), '') as storage_id,
        nullif(trim(anzeige_name_der_einheit), '') as unit_name,

        -- operational status (German value + English code)
        nullif(trim(betriebs_status), '') as status_de,
        case trim(betriebs_status)
            when 'In Betrieb' then 'operational'
            when 'In Planung' then 'planned'
            when 'Endgültig stillgelegt' then 'decommissioned'
            else 'unknown'
        end as status_code,

        -- energy carrier (German value + English code; storage detail later)
        nullif(trim(energietraeger), '') as energy_carrier_de,
        case trim(energietraeger)
            when 'Wind' then 'wind'
            when 'Solare Strahlungsenergie' then 'solar'
            when 'Biomasse' then 'biomass'
            when 'Speicher' then 'storage'
            else 'unknown'
        end as energy_carrier_code,
        nullif(trim(speichertechnologie), '') as storage_technology_de,
        case
            when nullif(trim(speichertechnologie), '') = 'Batterie' then 'battery'
            when nullif(trim(speichertechnologie), '') = 'Wasserstoffspeicher'
                then 'hydrogen_storage'
            when nullif(trim(speichertechnologie), '') is not null then 'other_storage'
            when trim(energietraeger) = 'Speicher' then 'other_storage'
            else null
        end as storage_technology_code,

        -- power and capacity (German decimal comma → NUMERIC)
        {{ parse_decimal_comma('bruttoleistung_der_einheit') }} as gross_power_kw,
        {{ parse_decimal_comma('nettonennleistung_der_einheit') }} as net_power_kw,
        {{ parse_decimal_comma('nutzbare_speicherkapazitaet_in_kwh') }} as storage_capacity_kwh,

        -- dates (DD/MM/YYYY → DATE)
        {{ parse_european_date('inbetriebnahmedatum_der_einheit') }} as commissioning_date,
        {{ parse_european_date('inbetriebnahmedatum_der_einheit_am_aktuellen_standort') }}
            as commissioning_date_at_site,
        {{ parse_european_date('registrierungsdatum_der_einheit') }} as registration_date,
        {{ parse_european_date('datum_der_geplanten_inbetriebnahme') }} as planned_commissioning_date,
        {{ parse_european_date('datum_der_endgueltigen_stilllegung') }} as decommissioned_date,
        {{ parse_european_date('letzte_aktualisierung') }} as last_updated_at,

        -- geography
        nullif(trim(gemeindeschluessel), '') as municipality_id,
        nullif(trim(gemeinde), '') as municipality_name,
        nullif(trim(landkreis), '') as district,
        nullif(trim(bundesland), '') as federal_state,
        nullif(trim(postleitzahl), '') as postal_code,
        nullif(trim(ort), '') as city,
        nullif(trim(strasse), '') as street,
        nullif(trim(hausnummer), '') as house_number,
        {{ parse_decimal_comma('koordinate_breitengrad_wgs84') }} as latitude,
        {{ parse_decimal_comma('koordinate_laengengrad_wgs84') }} as longitude,

        -- technology fields needed for Intermediate / Marts (v1)
        nullif(trim(technologie_der_stromerzeugung), '') as generation_technology,
        nullif(trim(art_der_solaranlage), '') as solar_system_type,
        safe_cast(nullif(trim(anzahl_der_solar_module), '') as int64) as solar_module_count,
        nullif(trim(name_des_solarparks), '') as solar_park_name,
        nullif(trim(name_des_windparks), '') as wind_park_name,
        nullif(trim(wind_an_land_oder_auf_see), '') as wind_onshore_or_offshore,
        {{ parse_decimal_comma('nabenhoehe_der_windenergieanlage') }} as hub_height_m,
        {{ parse_decimal_comma('rotordurchmesser_der_windenergieanlage') }} as rotor_diameter_m,
        nullif(trim(hersteller_der_windenergieanlage), '') as wind_turbine_manufacturer,
        nullif(trim(typenbezeichnung), '') as wind_turbine_type,
        nullif(trim(hauptbrennstoff_der_einheit), '') as main_fuel,
        nullif(trim(spannungsebene), '') as voltage_level,

        -- lineage (set at Raw load; preserved)
        source_file,
        snapshot_date,
        ingested_at

    from source

)

select * from renamed
