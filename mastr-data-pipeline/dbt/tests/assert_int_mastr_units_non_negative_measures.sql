-- Capacity-related measures must be non-negative when present.

select
    snapshot_date,
    unit_id,
    generation_power_kw,
    storage_power_kw,
    storage_capacity_kwh,
    gross_power_kw,
    net_power_kw
from {{ ref('int_mastr_units') }}
where
    (generation_power_kw is not null and generation_power_kw < 0)
    or (storage_power_kw is not null and storage_power_kw < 0)
    or (storage_capacity_kwh is not null and storage_capacity_kwh < 0)
    or (gross_power_kw is not null and gross_power_kw < 0)
    or (net_power_kw is not null and net_power_kw < 0)
