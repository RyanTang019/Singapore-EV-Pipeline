{# One row per carpark per lot type per snapshot (deduped upstream in
   int_carpark_tagged). Grain (batch_id, carpark_id, lot_type). Measure:
   available_lots. Surrogate key last so bare columns precede the md5 (ST06). #}

{{ config(materialized='table') }}

select
    batch_id,
    carpark_id,
    lot_type,
    snapshot_time,
    planning_area,
    development,
    latitude,
    longitude,
    snapshot_date,
    hour_of_day,
    day_of_week,

    available_lots,

    to_hex(md5(concat(batch_id, '|', carpark_id, '|', lot_type)))
        as carpark_availability_key
from {{ ref('int_carpark_tagged') }}
