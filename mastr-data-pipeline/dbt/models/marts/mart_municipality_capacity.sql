{{ config(materialized='table') }}

/*
  Municipality capacity for the latest complete snapshot only.
  Operational installations only; unknown energy sources excluded from totals.
  Generation kW, storage kW, and storage kWh remain separate.
*/

with latest_complete as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('complete_snapshots') }}

),

operational_units as (

    select
        f.municipality_id,
        f.generation_power_kw,
        f.storage_power_kw,
        f.storage_capacity_kwh,
        e.energy_source_code,
        e.energy_source_group
    from {{ ref('fct_mastr_units') }} as f
    inner join latest_complete as l
        on f.snapshot_date = l.snapshot_date
    inner join {{ ref('dim_energy_source') }} as e
        on f.energy_source_id = e.energy_source_id
    where f.is_operational = true
      and e.energy_source_group in ('generation', 'storage')

)

select
    m.municipality_id,
    m.municipality_name,
    m.district,
    m.federal_state,
    l.snapshot_date,
    coalesce(
        sum(
            case
                when o.energy_source_group = 'generation' then o.generation_power_kw
            end
        ),
        0
    ) as operational_generation_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'wind' then o.generation_power_kw
            end
        ),
        0
    ) as operational_wind_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'solar' then o.generation_power_kw
            end
        ),
        0
    ) as operational_solar_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'biomass' then o.generation_power_kw
            end
        ),
        0
    ) as operational_biomass_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_group = 'storage' then o.storage_power_kw
            end
        ),
        0
    ) as operational_storage_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_group = 'storage' then o.storage_capacity_kwh
            end
        ),
        0
    ) as operational_storage_capacity_kwh,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'battery' then o.storage_power_kw
            end
        ),
        0
    ) as operational_battery_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'battery' then o.storage_capacity_kwh
            end
        ),
        0
    ) as operational_battery_capacity_kwh,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'hydrogen_storage' then o.storage_power_kw
            end
        ),
        0
    ) as operational_hydrogen_storage_power_kw,
    coalesce(
        sum(
            case
                when o.energy_source_code = 'hydrogen_storage' then o.storage_capacity_kwh
            end
        ),
        0
    ) as operational_hydrogen_storage_capacity_kwh,
    countif(o.energy_source_group = 'generation') as operational_generation_unit_count,
    countif(o.energy_source_group = 'storage') as operational_storage_unit_count
from {{ ref('dim_municipality') }} as m
cross join latest_complete as l
left join operational_units as o
    on m.municipality_id = o.municipality_id
group by
    m.municipality_id,
    m.municipality_name,
    m.district,
    m.federal_state,
    l.snapshot_date
