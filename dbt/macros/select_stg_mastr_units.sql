{#
  Shared Staging select list: German→English renames, casts, and codes.
  ``relation_alias`` is the alias of the Raw source relation/CTE.
#}
{% macro select_stg_mastr_units(relation_alias='source') %}
        {{ relation_alias }}.mastr_nr_der_einheit as unit_id,
        nullif(trim({{ relation_alias }}.mastr_nr_der_speichereinheit), '') as storage_id,
        nullif(trim({{ relation_alias }}.anzeige_name_der_einheit), '') as unit_name,

        nullif(trim({{ relation_alias }}.betriebs_status), '') as status_de,
        case trim({{ relation_alias }}.betriebs_status)
            when 'In Betrieb' then 'operational'
            when 'In Planung' then 'planned'
            when 'Endgültig stillgelegt' then 'decommissioned'
            when 'Vorübergehend stillgelegt' then 'temporarily_decommissioned'
            else 'unknown'
        end as status_code,

        nullif(trim({{ relation_alias }}.energietraeger), '') as energy_carrier_de,
        case trim({{ relation_alias }}.energietraeger)
            when 'Wind' then 'wind'
            when 'Solare Strahlungsenergie' then 'solar'
            when 'Biomasse' then 'biomass'
            when 'Speicher' then 'storage'
            else 'unknown'
        end as energy_carrier_code,
        nullif(trim({{ relation_alias }}.speichertechnologie), '') as storage_technology_de,
        case
            when nullif(trim({{ relation_alias }}.speichertechnologie), '') = 'Batterie'
                then 'battery'
            when nullif(trim({{ relation_alias }}.speichertechnologie), '') = 'Wasserstoffspeicher'
                then 'hydrogen_storage'
            when nullif(trim({{ relation_alias }}.speichertechnologie), '') is not null
                then 'other_storage'
            when trim({{ relation_alias }}.energietraeger) = 'Speicher' then 'other_storage'
            else null
        end as storage_technology_code,

        {{ parse_decimal_comma(relation_alias ~ '.bruttoleistung_der_einheit') }} as gross_power_kw,
        {{ parse_decimal_comma(relation_alias ~ '.nettonennleistung_der_einheit') }} as net_power_kw,
        {{ parse_decimal_comma(relation_alias ~ '.nutzbare_speicherkapazitaet_in_kwh') }}
            as storage_capacity_kwh,

        {{ parse_european_date(relation_alias ~ '.inbetriebnahmedatum_der_einheit') }}
            as commissioning_date,
        {{ parse_european_date(relation_alias ~ '.inbetriebnahmedatum_der_einheit_am_aktuellen_standort') }}
            as commissioning_date_at_site,
        {{ parse_european_date(relation_alias ~ '.registrierungsdatum_der_einheit') }}
            as registration_date,
        {{ parse_european_date(relation_alias ~ '.datum_der_geplanten_inbetriebnahme') }}
            as planned_commissioning_date,
        {{ parse_european_date(relation_alias ~ '.datum_der_endgueltigen_stilllegung') }}
            as decommissioned_date,
        {{ parse_european_date(relation_alias ~ '.letzte_aktualisierung') }} as last_updated_at,

        nullif(trim({{ relation_alias }}.gemeindeschluessel), '') as municipality_id,
        nullif(trim({{ relation_alias }}.gemeinde), '') as municipality_name,
        nullif(trim({{ relation_alias }}.landkreis), '') as district,
        nullif(trim({{ relation_alias }}.bundesland), '') as federal_state,
        nullif(trim({{ relation_alias }}.postleitzahl), '') as postal_code,
        nullif(trim({{ relation_alias }}.ort), '') as city,
        nullif(trim({{ relation_alias }}.strasse), '') as street,
        nullif(trim({{ relation_alias }}.hausnummer), '') as house_number,
        {{ parse_decimal_comma(relation_alias ~ '.koordinate_breitengrad_wgs84') }} as latitude,
        {{ parse_decimal_comma(relation_alias ~ '.koordinate_laengengrad_wgs84') }} as longitude,

        nullif(trim({{ relation_alias }}.technologie_der_stromerzeugung), '')
            as generation_technology,
        nullif(trim({{ relation_alias }}.art_der_solaranlage), '') as solar_system_type,
        safe_cast(
            nullif(trim({{ relation_alias }}.anzahl_der_solar_module), '') as int64
        ) as solar_module_count,
        nullif(trim({{ relation_alias }}.name_des_solarparks), '') as solar_park_name,
        nullif(trim({{ relation_alias }}.name_des_windparks), '') as wind_park_name,
        nullif(trim({{ relation_alias }}.wind_an_land_oder_auf_see), '')
            as wind_onshore_or_offshore,
        {{ parse_decimal_comma(relation_alias ~ '.nabenhoehe_der_windenergieanlage') }}
            as hub_height_m,
        {{ parse_decimal_comma(relation_alias ~ '.rotordurchmesser_der_windenergieanlage') }}
            as rotor_diameter_m,
        nullif(trim({{ relation_alias }}.hersteller_der_windenergieanlage), '')
            as wind_turbine_manufacturer,
        nullif(trim({{ relation_alias }}.typenbezeichnung), '') as wind_turbine_type,
        nullif(trim({{ relation_alias }}.hauptbrennstoff_der_einheit), '') as main_fuel,
        nullif(trim({{ relation_alias }}.spannungsebene), '') as voltage_level,

        {{ relation_alias }}.source_file,
        {{ relation_alias }}.snapshot_date,
        {{ relation_alias }}.ingested_at
{% endmacro %}
