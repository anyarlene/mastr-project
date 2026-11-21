-- Generation and storage measures must not be mixed by energy_source_group.

select
    snapshot_date,
    unit_id,
    energy_source_group,
    generation_power_kw,
    storage_power_kw,
    storage_capacity_kwh
from {{ ref('int_mastr_units') }}
where
    (
        energy_source_group = 'generation'
        and (storage_power_kw is not null or storage_capacity_kwh is not null)
    )
    or (
        energy_source_group = 'storage'
        and generation_power_kw is not null
    )
    or (
        energy_source_group = 'storage'
        and storage_power_kw is null
    )
    or (
        energy_source_group = 'unknown'
        and (
            generation_power_kw is not null
            or storage_power_kw is not null
            or storage_capacity_kwh is not null
        )
    )
