{{ config(materialized='view') }}

/*
  Snapshot-based CDC between consecutive all_statuses complete snapshots.

  Change types:
    INSERT            — unit_id only in the later snapshot
    UPDATE            — unit_id in both; tracked attributes differ (null-safe)
    DELETE_CANDIDATE  — unit_id only in the earlier snapshot (not confirmed delete)
    UNCHANGED         — unit_id in both; tracked attributes equal

  Tracked attributes: status_code, net_power_kw, storage_capacity_kwh, municipality_id.
  Observation dates only (from_snapshot_date / to_snapshot_date).
  With a single eligible snapshot, this model returns zero rows.
*/

with eligible as (

    select snapshot_date
    from {{ ref('cdc_eligible_snapshots') }}

),

ordered as (

    select
        snapshot_date,
        lag(snapshot_date) over (order by snapshot_date) as previous_snapshot_date
    from eligible

),

pairs as (

    select
        previous_snapshot_date as from_snapshot_date,
        snapshot_date as to_snapshot_date
    from ordered
    where previous_snapshot_date is not null

),

from_units as (

    select
        p.from_snapshot_date,
        p.to_snapshot_date,
        i.unit_id,
        i.source_file,
        i.status_code,
        i.net_power_kw,
        i.storage_capacity_kwh,
        i.municipality_id
    from pairs as p
    inner join {{ ref('int_mastr_units') }} as i
        on i.snapshot_date = p.from_snapshot_date

),

to_units as (

    select
        p.from_snapshot_date,
        p.to_snapshot_date,
        i.unit_id,
        i.source_file,
        i.status_code,
        i.net_power_kw,
        i.storage_capacity_kwh,
        i.municipality_id
    from pairs as p
    inner join {{ ref('int_mastr_units') }} as i
        on i.snapshot_date = p.to_snapshot_date

),

compared as (

    select
        coalesce(f.from_snapshot_date, t.from_snapshot_date) as from_snapshot_date,
        coalesce(f.to_snapshot_date, t.to_snapshot_date) as to_snapshot_date,
        coalesce(f.unit_id, t.unit_id) as unit_id,
        coalesce(t.source_file, f.source_file) as source_file,
        case
            when f.unit_id is null then 'INSERT'
            when t.unit_id is null then 'DELETE_CANDIDATE'
            when f.status_code is distinct from t.status_code
                or f.net_power_kw is distinct from t.net_power_kw
                or f.storage_capacity_kwh is distinct from t.storage_capacity_kwh
                or f.municipality_id is distinct from t.municipality_id
                then 'UPDATE'
            else 'UNCHANGED'
        end as change_type,
        f.status_code as before_status_code,
        t.status_code as after_status_code,
        f.net_power_kw as before_net_power_kw,
        t.net_power_kw as after_net_power_kw,
        f.storage_capacity_kwh as before_storage_capacity_kwh,
        t.storage_capacity_kwh as after_storage_capacity_kwh,
        f.municipality_id as before_municipality_id,
        t.municipality_id as after_municipality_id
    from from_units as f
    full outer join to_units as t
        on f.unit_id = t.unit_id
        and f.from_snapshot_date = t.from_snapshot_date
        and f.to_snapshot_date = t.to_snapshot_date

)

select
    from_snapshot_date,
    to_snapshot_date,
    unit_id,
    source_file,
    change_type,
    before_status_code,
    after_status_code,
    before_net_power_kw,
    after_net_power_kw,
    before_storage_capacity_kwh,
    after_storage_capacity_kwh,
    before_municipality_id,
    after_municipality_id
from compared
