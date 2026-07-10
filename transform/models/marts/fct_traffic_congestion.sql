{# Congestion aggregated to (planning_area, snapshot). All congestion signal
   uses speed_band_for_metrics (SpeedBand 0 nulled) so no-reading links never
   count as congestion. Links tagged to no area (planning_area NULL) excluded. #}

{{ config(materialized='table') }}

with joined as (
    select
        s.batch_id,
        s.snapshot_time,
        s.speed_band_for_metrics,
        s.is_no_reading,
        l.planning_area
    from {{ ref('stg_traffic_speed_bands') }} as s
    inner join {{ ref('int_traffic_links') }} as l
        on s.link_id = l.link_id
    where l.planning_area is not null
)

select
    batch_id,
    planning_area,
    to_hex(md5(concat(batch_id, '|', planning_area)))
        as traffic_congestion_key,

    any_value(snapshot_time) as snapshot_time,
    {{ time_features('any_value(snapshot_time)') }},

    avg(speed_band_for_metrics) as mean_speed_band,
    safe_divide(
        countif(speed_band_for_metrics <= 2),
        countif(speed_band_for_metrics is not null)
    ) as congested_link_rate,
    countif(speed_band_for_metrics is not null) as link_count,
    countif(is_no_reading) as no_reading_link_count
from joined
group by batch_id, planning_area
