{{ config(materialized='table') }}

select
    status_id,
    status_code,
    status_label,
    is_operational
from {{ ref('seed_statuses') }}
