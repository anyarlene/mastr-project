-- Mart must include every municipality in dim_municipality (no dropouts).

select
    d.municipality_id
from {{ ref('dim_municipality') }} as d
left join {{ ref('mart_municipality_capacity') }} as m
    on d.municipality_id = m.municipality_id
where m.municipality_id is null
