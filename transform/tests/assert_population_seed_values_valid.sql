select
    population_release_key,
    planning_area,
    resident_population
from {{ ref('stg_planning_area_population') }}
where resident_population < 0
