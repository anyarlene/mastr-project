{{ config(materialized='ephemeral') }}

/*
  CDC-eligible snapshot dates.

  A snapshot is eligible when:
    1) it is complete (complete_snapshots), and
    2) export_scope = all_statuses (seed_snapshot_metadata).

  November 9 (legacy_mixed_filters) is excluded even though it is complete.
  CDC comparisons start from 2026-11-16 as the first eligible baseline.
*/

select
    c.snapshot_date
from {{ ref('complete_snapshots') }} as c
inner join {{ ref('seed_snapshot_metadata') }} as m
    on c.snapshot_date = m.snapshot_date
where m.export_scope = 'all_statuses'
