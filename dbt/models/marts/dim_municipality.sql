{{ config(materialized='table') }}

/*
  One row per municipality_id ever observed in Intermediate (historical preserved).

  Attributes are chosen deterministically:
    1) prefer the latest complete snapshot when the municipality appears there
    2) otherwise the most recent snapshot_date
    3) then municipality_name, district, federal_state, unit_id (stable tie-break)
*/

with latest_complete as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('complete_snapshots') }}

),

ranked as (

    select
        i.municipality_id,
        i.municipality_name,
        i.district,
        i.federal_state,
        row_number() over (
            partition by i.municipality_id
            order by
                case
                    when i.snapshot_date = lc.snapshot_date then 0
                    else 1
                end asc,
                i.snapshot_date desc,
                i.municipality_name asc nulls last,
                i.district asc nulls last,
                i.federal_state asc nulls last,
                i.unit_id asc
        ) as attribute_rank
    from {{ ref('int_mastr_units') }} as i
    cross join latest_complete as lc

)

select
    municipality_id,
    municipality_name,
    district,
    federal_state
from ranked
where attribute_rank = 1
