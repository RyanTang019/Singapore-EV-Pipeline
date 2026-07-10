{# The spatial hub: one row per planning area, geometry ready for ST_COVERS.
   area_sqkm = ST_AREA (square metres) / 1e6. Materialized as a table because the
   tagging macro reads it repeatedly. #}

{{ config(materialized='table') }}

select
    planning_area,
    region,
    boundary,
    st_area(boundary) / 1e6 as area_sqkm
from {{ ref('stg_planning_areas') }}
