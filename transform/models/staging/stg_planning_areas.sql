{# One row per URA planning area. Parses the seed's WKT text into a BigQuery
   GEOGRAPHY. make_valid => true is REQUIRED: URA polygons self-intersect and a
   bare ST_GEOGFROMTEXT errors on them. No tests here — the grain is proven at
   dim_planning_area. #}

{{ config(materialized='view') }}

select
    planning_area,
    region,
    st_geogfromtext(boundary_wkt, make_valid => true) as boundary
from {{ ref('planning_areas') }}
