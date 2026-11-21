-- Every configured snapshot expectation set must either be complete
-- (all four files aligned across Raw/Staging/Intermediate) or absent from
-- Intermediate. Fail when Intermediate has a snapshot that is not complete.

select
    i.snapshot_date,
    count(distinct i.source_file) as intermediate_files,
    count(c.snapshot_date) as complete_flag
from {{ ref('int_mastr_units') }} as i
left join {{ ref('complete_snapshots') }} as c
    on i.snapshot_date = c.snapshot_date
group by i.snapshot_date
having count(c.snapshot_date) = 0
