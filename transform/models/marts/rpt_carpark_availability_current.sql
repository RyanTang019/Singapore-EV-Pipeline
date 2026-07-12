{# Current car-lot reporting table for Looker scorecards and point maps.
   Lot type C is part of this reporting contract. as_of_sgt is text so
   historical date controls cannot suppress the already-current result. #}

{{ config(materialized='table') }}

with latest_batch as (
    select batch_id
    from {{ ref('fct_carpark_availability') }}
    group by batch_id
    order by max(snapshot_time) desc, batch_id desc
    limit 1
)

select
    f.batch_id,
    f.carpark_availability_key,
    f.carpark_id,
    f.lot_type,
    f.development,
    f.planning_area,
    f.latitude,
    f.longitude,
    f.available_lots,
    format_timestamp(
        '%Y-%m-%d %H:%M:%S',
        f.snapshot_time,
        'Asia/Singapore'
    ) as as_of_sgt,
    safe.st_geogpoint(f.longitude, f.latitude) as location
from {{ ref('fct_carpark_availability') }} as f
inner join latest_batch
    on f.batch_id = latest_batch.batch_id
where f.lot_type = 'C'
