select
    population_release_key,
    planning_area,
    resident_population,
    population_density_per_sqkm,
    population_data_status
from {{ ref('fct_planning_area_population') }}
where
    area_sqkm <= 0
    or resident_population < 0
    or population_density_per_sqkm < 0
    or (population_data_status = 'missing' and resident_population is not null)
    or (population_data_status = 'reported_zero' and resident_population != 0)
    or (population_data_status = 'reported' and resident_population <= 0)
    or (
        resident_population is null
        and population_density_per_sqkm is not null
    )
