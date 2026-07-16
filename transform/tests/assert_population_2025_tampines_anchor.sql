select
    population_release_key,
    planning_area,
    resident_population
from {{ ref('fct_planning_area_population') }}
where
    population_year = 2025
    and planning_area = 'TAMPINES'
    and resident_population != 290090
