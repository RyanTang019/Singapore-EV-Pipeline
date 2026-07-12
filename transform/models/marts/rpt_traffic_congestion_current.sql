{# Current planning-area traffic table for Looker's filled map and scorecards.
   Boundary is joined once at build time; as_of_sgt remains text so historical
   report date controls cannot filter the current snapshot. #}

{{ config(materialized='table') }}

with latest_batch as (
    select batch_id
    from {{ ref('fct_traffic_congestion') }}
    group by batch_id
    order by max(snapshot_time) desc, batch_id desc
    limit 1
)

select
    f.batch_id,
    f.traffic_congestion_key,
    f.planning_area,
    d.region,
    d.area_sqkm,
    f.mean_speed_band,
    f.congested_link_rate,
    f.link_count,
    f.no_reading_link_count,
    d.boundary,
    format_timestamp(
        '%Y-%m-%d %H:%M:%S',
        f.snapshot_time,
        'Asia/Singapore'
    ) as as_of_sgt
from {{ ref('fct_traffic_congestion') }} as f
inner join latest_batch
    on f.batch_id = latest_batch.batch_id
inner join {{ ref('dim_planning_area') }} as d
    on f.planning_area = d.planning_area
