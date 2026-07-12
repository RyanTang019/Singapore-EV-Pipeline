{# Current-state reporting table for Looker scorecards and point maps.
   Deliberately exposes the as-of time as text: report-level date controls must
   not filter a model that already selects exactly one latest batch. #}

{{ config(materialized='table') }}

with latest_batch as (
    select batch_id
    from {{ ref('fct_ev_location_availability') }}
    group by batch_id
    order by max(snapshot_time) desc, batch_id desc
    limit 1
)

select
    f.batch_id,
    f.location_availability_key,
    f.postal_code,
    f.location_name,
    f.address,
    f.planning_area,
    f.latitude,
    f.longitude,
    f.total_connectors,
    f.available_connectors,
    f.occupied_connectors,
    f.unavailable_connectors,
    f.availability_rate,
    format_timestamp(
        '%Y-%m-%d %H:%M:%S',
        f.snapshot_time,
        'Asia/Singapore'
    ) as as_of_sgt,
    safe.st_geogpoint(f.longitude, f.latitude) as location
from {{ ref('fct_ev_location_availability') }} as f
inner join latest_batch
    on f.batch_id = latest_batch.batch_id
