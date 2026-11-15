-- Mart snapshot_date must equal the latest complete snapshot (single date).

with latest_complete as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('complete_snapshots') }}

),

mart_dates as (

    select distinct snapshot_date
    from {{ ref('mart_municipality_capacity') }}

)

select
    m.snapshot_date as mart_snapshot_date,
    l.snapshot_date as latest_complete_snapshot_date
from mart_dates as m
cross join latest_complete as l
where m.snapshot_date != l.snapshot_date
   or (select count(*) from mart_dates) != 1
