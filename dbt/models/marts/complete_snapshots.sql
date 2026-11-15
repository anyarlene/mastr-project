{{ config(materialized='ephemeral') }}

/*
  Complete snapshots for Gold reporting.

  A snapshot_date is complete only when:
    1) all four expected source files are present
    2) Intermediate row counts match seed_snapshot_expectations
       (generated from config/snapshots.json)
    3) Raw, Staging, and Intermediate counts agree per source_file
       (layer consistency — not row counts against expectations alone)
*/

with expected as (

    select
        snapshot_date,
        source_file,
        expected_row_count
    from {{ ref('seed_snapshot_expectations') }}

),

raw_counts as (

    select
        snapshot_date,
        source_file,
        count(*) as row_count
    from {{ source('mastr_raw', 'raw_mastr_units') }}
    group by snapshot_date, source_file

),

staging_counts as (

    select
        snapshot_date,
        source_file,
        count(*) as row_count
    from {{ ref('stg_mastr_units') }}
    group by snapshot_date, source_file

),

intermediate_counts as (

    select
        snapshot_date,
        source_file,
        count(*) as row_count
    from {{ ref('int_mastr_units') }}
    group by snapshot_date, source_file

),

aligned as (

    select
        e.snapshot_date,
        e.source_file
    from expected as e
    inner join raw_counts as r
        on e.snapshot_date = r.snapshot_date
        and e.source_file = r.source_file
        and e.expected_row_count = r.row_count
    inner join staging_counts as s
        on e.snapshot_date = s.snapshot_date
        and e.source_file = s.source_file
        and e.expected_row_count = s.row_count
    inner join intermediate_counts as i
        on e.snapshot_date = i.snapshot_date
        and e.source_file = i.source_file
        and e.expected_row_count = i.row_count

)

select
    snapshot_date
from aligned
group by snapshot_date
having count(*) = 4
