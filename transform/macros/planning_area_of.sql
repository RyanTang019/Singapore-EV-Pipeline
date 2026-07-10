{% macro planning_area_of(lon, lat) %}
(
    select d.planning_area
    from {{ ref('dim_planning_area') }} as d
    where st_covers(d.boundary, safe.st_geogpoint({{ lon }}, {{ lat }}))
    order by d.planning_area
    limit 1
)
{% endmacro %}
