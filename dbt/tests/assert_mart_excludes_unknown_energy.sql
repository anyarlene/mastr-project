-- Generation subtotals must add up (unknown excluded from both sides).
-- Storage battery + hydrogen may be less than total storage when other_storage exists.

select
    municipality_id,
    operational_generation_power_kw,
    operational_wind_power_kw,
    operational_solar_power_kw,
    operational_biomass_power_kw,
    operational_storage_power_kw,
    operational_battery_power_kw,
    operational_hydrogen_storage_power_kw
from {{ ref('mart_municipality_capacity') }}
where
    operational_generation_power_kw
        != operational_wind_power_kw
         + operational_solar_power_kw
         + operational_biomass_power_kw
    or operational_battery_power_kw + operational_hydrogen_storage_power_kw
        > operational_storage_power_kw
