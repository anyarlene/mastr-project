-- Generation / storage measures must respect energy_source_group.

select
    f.snapshot_date,
    f.unit_id,
    e.energy_source_group,
    f.generation_power_kw,
    f.storage_power_kw,
    f.storage_capacity_kwh
from {{ ref('fct_mastr_units') }} as f
inner join {{ ref('dim_energy_source') }} as e
    on f.energy_source_id = e.energy_source_id
where
    (
        e.energy_source_group = 'generation'
        and (f.storage_power_kw is not null or f.storage_capacity_kwh is not null)
    )
    or (
        e.energy_source_group = 'storage'
        and f.generation_power_kw is not null
    )
    or (
        e.energy_source_group = 'unknown'
        and (
            f.generation_power_kw is not null
            or f.storage_power_kw is not null
            or f.storage_capacity_kwh is not null
        )
    )
