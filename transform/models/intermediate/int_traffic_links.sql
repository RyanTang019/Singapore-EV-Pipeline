{# One row per physical road link -> planning_area, built ONCE as a table (not a
   view — a view would re-run the spatial join on every downstream read, and there
   are ~57k links joined against 5.4M observations). Canonical geometry = the
   LATEST start/end coords per link_id (deterministic tie-break enforces the
   one-row-per-link grain even if a link's geometry drifts). Tag the midpoint via
   the shared distinct-point INNER spatial join + min() tie-break + LEFT equi-join
   back so links outside all areas survive with planning_area NULL. #}

{{ config(materialized='table') }}

with latest_geom as (
    select
        link_id,
        start_latitude,
        start_longitude,
        end_latitude,
        end_longitude,
        row_number() over (
            partition by link_id
            order by snapshot_time desc, ingested_at desc, batch_id desc
        ) as rn
    from {{ ref('stg_traffic_speed_bands') }}
),

midpoints as (
    select
        link_id,
        (start_latitude + end_latitude) / 2 as mid_lat,
        (start_longitude + end_longitude) / 2 as mid_lon
    from latest_geom
    where rn = 1
),

points as (
    select distinct
        mid_lon,
        mid_lat
    from midpoints
),

matches as (
    select
        p.mid_lon,
        p.mid_lat,
        min(d.planning_area) as planning_area
    from points as p
    inner join {{ ref('dim_planning_area') }} as d
        on {{ planning_area_covers('d.boundary', 'p.mid_lon', 'p.mid_lat') }}
    group by p.mid_lon, p.mid_lat
)

select
    m.link_id,
    m.mid_lat,
    m.mid_lon,
    matches.planning_area
from midpoints as m
left join matches
    on
        m.mid_lon = matches.mid_lon
        and m.mid_lat = matches.mid_lat
