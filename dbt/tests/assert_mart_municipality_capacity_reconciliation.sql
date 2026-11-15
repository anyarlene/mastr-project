-- Mart totals must reconcile to operational fact measures on the same snapshot.

with latest_complete as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('complete_snapshots') }}

),

fact_totals as (

    select
        sum(
            case
                when e.energy_source_group = 'generation' then f.generation_power_kw
            end
        ) as generation_power_kw,
        sum(
            case
                when e.energy_source_group = 'storage' then f.storage_power_kw
            end
        ) as storage_power_kw,
        sum(
            case
                when e.energy_source_group = 'storage' then f.storage_capacity_kwh
            end
        ) as storage_capacity_kwh,
        sum(
            case
                when e.energy_source_code = 'battery' then f.storage_power_kw
            end
        ) as battery_power_kw,
        sum(
            case
                when e.energy_source_code = 'hydrogen_storage' then f.storage_power_kw
            end
        ) as hydrogen_power_kw
    from {{ ref('fct_mastr_units') }} as f
    inner join latest_complete as l
        on f.snapshot_date = l.snapshot_date
    inner join {{ ref('dim_energy_source') }} as e
        on f.energy_source_id = e.energy_source_id
    where f.is_operational = true
      and e.energy_source_group in ('generation', 'storage')

),

mart_totals as (

    select
        sum(operational_generation_power_kw) as generation_power_kw,
        sum(operational_storage_power_kw) as storage_power_kw,
        sum(operational_storage_capacity_kwh) as storage_capacity_kwh,
        sum(operational_battery_power_kw) as battery_power_kw,
        sum(operational_hydrogen_storage_power_kw) as hydrogen_power_kw
    from {{ ref('mart_municipality_capacity') }}

)

select
    f.generation_power_kw as fact_generation_power_kw,
    m.generation_power_kw as mart_generation_power_kw,
    f.storage_power_kw as fact_storage_power_kw,
    m.storage_power_kw as mart_storage_power_kw,
    f.storage_capacity_kwh as fact_storage_capacity_kwh,
    m.storage_capacity_kwh as mart_storage_capacity_kwh,
    f.battery_power_kw as fact_battery_power_kw,
    m.battery_power_kw as mart_battery_power_kw,
    f.hydrogen_power_kw as fact_hydrogen_power_kw,
    m.hydrogen_power_kw as mart_hydrogen_power_kw
from fact_totals as f
cross join mart_totals as m
where
    coalesce(f.generation_power_kw, 0) != coalesce(m.generation_power_kw, 0)
    or coalesce(f.storage_power_kw, 0) != coalesce(m.storage_power_kw, 0)
    or coalesce(f.storage_capacity_kwh, 0) != coalesce(m.storage_capacity_kwh, 0)
    or coalesce(f.battery_power_kw, 0) != coalesce(m.battery_power_kw, 0)
    or coalesce(f.hydrogen_power_kw, 0) != coalesce(m.hydrogen_power_kw, 0)
