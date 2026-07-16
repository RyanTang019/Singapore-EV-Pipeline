with releases as (

    select distinct population_release_key
    from {{ ref('stg_planning_area_population_releases') }}

),

expected as (

    select
        releases.population_release_key,
        planning_areas.planning_area
    from releases
    cross join {{ ref('dim_planning_area') }} as planning_areas

),

actual as (

    select
        population_release_key,
        planning_area
    from {{ ref('stg_planning_area_population') }}

)

select
    coalesce(expected.population_release_key, actual.population_release_key)
        as population_release_key,
    coalesce(expected.planning_area, actual.planning_area) as planning_area
from expected
full outer join actual
    on
        expected.population_release_key = actual.population_release_key
        and expected.planning_area = actual.planning_area
where
    expected.population_release_key is null
    or actual.population_release_key is null
