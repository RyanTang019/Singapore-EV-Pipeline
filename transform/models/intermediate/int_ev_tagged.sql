{# stg_ev_charger_availability + planning_area + SGT time features. Grain
   unchanged (connector per snapshot). View.
   Tagging = distinct points -> INNER spatial join to dim_planning_area (the
   optimized join shape) -> min(planning_area) as the alphabetical tie-break for
   points covered by >1 area -> LEFT equi-join back so unmatched / null / offshore
   / invalid-coordinate rows survive with planning_area NULL. #}

{{ config(materialized='view') }}

with src as (
    select * from {{ ref('stg_ev_charger_availability') }}
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
