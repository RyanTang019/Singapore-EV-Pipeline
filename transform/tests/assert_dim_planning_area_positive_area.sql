-- Fails on any non-positive / null area (coordinate-order or projection bug).
select
    planning_area,
    area_sqkm
from {{ ref('dim_planning_area') }}
where area_sqkm is null or area_sqkm <= 0
