with release_counts as (

    select
        population_release_key,
        count(*) as row_count
    from {{ ref('fct_planning_area_population') }}
    group by population_release_key

),

year_counts as (

    select
        population_year,
        count(distinct population_release_key) as release_count
    from {{ ref('fct_planning_area_population') }}
    group by population_year

)

select
    population_release_key as failed_key,
    row_count as failed_count
from release_counts
where row_count != 55

union all

select
    cast(population_year as string) as failed_key,
    release_count as failed_count
from year_counts
where release_count != 1
