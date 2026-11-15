{{ config(materialized='view') }}

/*
  Intermediate (Silver): English-only business classification and measures.

  Inputs from Staging already use English codes. No German→English mapping here.
  Unknown energy carriers are preserved as energy_source_code/group = unknown
  and excluded from generation/storage capacity measures.
*/

with staging as (

    select * from {{ ref('stg_mastr_units') }}

),

enriched as (

    select
        -- identifiers
        unit_id,
        storage_id,
        unit_name,

        -- status
        status_code,
        (status_code = 'operational') as is_operational,

        -- English classification inputs from Staging
        energy_carrier_code,
        storage_technology_code,

        case
            when energy_carrier_code in ('wind', 'solar', 'biomass')
                then energy_carrier_code
            when energy_carrier_code = 'storage'
                then coalesce(storage_technology_code, 'other_storage')
            else 'unknown'
        end as energy_source_code,

        case
            when energy_carrier_code in ('wind', 'solar', 'biomass') then 'generation'
            when energy_carrier_code = 'storage' then 'storage'
            else 'unknown'
        end as energy_source_group,

        -- power measures (unknown group excluded from capacity measures)
        gross_power_kw,
        net_power_kw,
        case
            when energy_carrier_code in ('wind', 'solar', 'biomass') then net_power_kw
        end as generation_power_kw,
        case
            when energy_carrier_code = 'storage' then net_power_kw
        end as storage_power_kw,
        case
            when energy_carrier_code = 'storage' then storage_capacity_kwh
        end as storage_capacity_kwh,

        -- dates
        commissioning_date,
        commissioning_date_at_site,
        registration_date,
        planned_commissioning_date,
        decommissioned_date,
        last_updated_at,

        -- geography
        municipality_id,
        municipality_name,
        district,
        federal_state,
        postal_code,
        city,
        street,
        house_number,
        latitude,
        longitude,

        -- technology attributes for Marts
        generation_technology,
        solar_system_type,
        solar_module_count,
        solar_park_name,
        wind_park_name,
        wind_onshore_or_offshore,
        hub_height_m,
        rotor_diameter_m,
        wind_turbine_manufacturer,
        wind_turbine_type,
        main_fuel,
        voltage_level,

        -- lineage
        source_file,
        snapshot_date,
        ingested_at

    from staging

)

select * from enriched
