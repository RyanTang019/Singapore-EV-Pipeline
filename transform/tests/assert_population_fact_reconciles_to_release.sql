with fact_totals as (

    select
        population_release_key,
        count(*) as source_row_count,
        sum(resident_population) as generated_population_total
    from {{ ref('fct_planning_area_population') }}
    group by population_release_key

)

select
    fact_totals.population_release_key,
    fact_totals.source_row_count,
    releases.expected_planning_area_row_count,
    fact_totals.generated_population_total,
    releases.generated_planning_area_population_total,
    releases.national_resident_population,
    releases.max_national_reconciliation_difference
from fact_totals
inner join {{ ref('stg_planning_area_population_releases') }} as releases
    on
        fact_totals.population_release_key = releases.population_release_key
where
    fact_totals.source_row_count != releases.expected_planning_area_row_count
    or fact_totals.generated_population_total
    != releases.generated_planning_area_population_total
    or abs(
        fact_totals.generated_population_total
        - releases.national_resident_population
    ) > releases.max_national_reconciliation_difference
