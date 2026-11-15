-- Within the latest complete snapshot, municipality attributes must not conflict.

with latest_complete as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('complete_snapshots') }}

),

conflicts as (

    select
        i.municipality_id,
        count(distinct concat(
            coalesce(i.municipality_name, ''),
            '|',
            coalesce(i.district, ''),
            '|',
            coalesce(i.federal_state, '')
        )) as attribute_variants
    from {{ ref('int_mastr_units') }} as i
    inner join latest_complete as l
        on i.snapshot_date = l.snapshot_date
    group by i.municipality_id
    having count(distinct concat(
        coalesce(i.municipality_name, ''),
        '|',
        coalesce(i.district, ''),
        '|',
        coalesce(i.federal_state, '')
    )) > 1

)

select *
from conflicts
