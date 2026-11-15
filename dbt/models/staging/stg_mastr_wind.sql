{{ config(materialized='view') }}

with source as (

    select * from {{ source('mastr_raw', 'raw_mastr_wind') }}

)

select
    {{ select_stg_mastr_units('source') }}
from source
