-- Intermediate row count must match Staging.

select
    staging_counts.row_count as staging_row_count,
    intermediate_counts.row_count as intermediate_row_count
from (
    select count(*) as row_count
    from {{ ref('stg_mastr_units') }}
) as staging_counts
cross join (
    select count(*) as row_count
    from {{ ref('int_mastr_units') }}
) as intermediate_counts
where staging_counts.row_count != intermediate_counts.row_count
