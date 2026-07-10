{# Boolean spatial predicate: does `boundary` (a GEOGRAPHY) cover the point at
   (lon, lat)? Kept in one place so every tagging model shares the same rule:
   - st_covers (not st_contains) tags points on a shared boundary edge.
   - safe.st_geogpoint returns NULL for null / out-of-range coords instead of
     erroring, so bad coordinates simply don't match any area.
   Use it as an INNER spatial join condition (BigQuery only optimizes INNER/CROSS
   spatial joins); the area selection itself is min(planning_area) in the model. #}

{% macro planning_area_covers(boundary, lon, lat) %}
st_covers(
    {{ boundary }},
    safe.st_geogpoint({{ lon }}, {{ lat }})
)
{% endmacro %}
