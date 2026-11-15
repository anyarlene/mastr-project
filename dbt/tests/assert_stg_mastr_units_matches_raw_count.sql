-- Source-to-staging row count consistency.
-- Fails when staging row count differs from Raw.

select
    raw_counts.row_count as raw_row_count,
    stg_counts.row_count as staging_row_count
from (
    select count(*) as row_count
    from {{ source('mastr_raw', 'raw_mastr_units') }}
) as raw_counts
cross join (
    select count(*) as row_count
    from {{ ref('stg_mastr_units') }}
) as stg_counts
where raw_counts.row_count != stg_counts.row_count
