{# Dedupe repeated (batch_id, carpark_id, lot_type) rows keeping the LATEST
   array position (last-observed — never max-lots, which is optimistically
   biased), then tag planning_area and add SGT time features. View.
   Tagging = distinct points -> INNER spatial join to dim_planning_area (the
   optimized join shape) -> min(planning_area) alphabetical tie-break -> LEFT
   equi-join back so unmatched / null / offshore rows survive with NULL. #}

{{ config(materialized='view') }}

with deduped as (
    select
        *,
        row_number() over (
            partition by batch_id, carpark_id, lot_type
            order by source_offset desc
        ) as rn
    from {{ ref('stg_carpark_availability') }}
),

src as (
    select
        batch_id,
        available_lots,
        latitude,
        longitude,
        snapshot_time,
        carpark_id,
        lot_type,
        development
    from deduped
    where rn = 1
),

points as (
    select distinct
        longitude,
        latitude
    from src
),

matches as (
    select
        p.longitude,
        p.latitude,
        min(d.planning_area) as planning_area
    from points as p
    inner join {{ ref('dim_planning_area') }} as d
        on {{ planning_area_covers('d.boundary', 'p.longitude', 'p.latitude') }}
    group by p.longitude, p.latitude
)

select
    src.*,
    matches.planning_area,
    {{ time_features('src.snapshot_time') }}
from src
left join matches
    on
        src.longitude = matches.longitude
        and src.latitude = matches.latitude
