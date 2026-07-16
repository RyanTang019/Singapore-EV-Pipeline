{{ config(materialized='table') }}

with releases as (

    select
        population_release_key,
        population_year,
        source_reference_date,
        source_published_date,
        source_retrieved_date,
        planning_geography_version
    from {{ ref('stg_planning_area_population_releases') }}

),

planning_areas as (

    select
        planning_area,
        region,
        area_sqkm
    from {{ ref('dim_planning_area') }}

),

population as (

    select
        population_release_key,
        planning_area,
        resident_population
    from {{ ref('stg_planning_area_population') }}

)

select
    releases.population_year,
    releases.population_release_key,
    releases.source_reference_date,
    releases.source_published_date,
    releases.source_retrieved_date,
    releases.planning_geography_version,
    planning_areas.planning_area,
    planning_areas.region,
    planning_areas.area_sqkm,
    population.resident_population,
    to_hex(
        md5(
            concat(
                releases.population_release_key,
                '|',
                planning_areas.planning_area
            )
        )
    ) as population_key,
    safe_divide(
        population.resident_population,
        planning_areas.area_sqkm
    ) as population_density_per_sqkm,
    case
        when population.resident_population is null then 'missing'
        when population.resident_population = 0 then 'reported_zero'
        else 'reported'
    end as population_data_status
from releases
cross join planning_areas
left join population
    on
        releases.population_release_key = population.population_release_key
        and planning_areas.planning_area = population.planning_area
