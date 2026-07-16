{{ config(materialized='view') }}

select
    cast(population_release_key as string) as population_release_key,
    cast(population_year as int64) as population_year,
    cast(planning_area as string) as planning_area,
    cast(resident_population as int64) as resident_population,
    to_hex(
        md5(
            concat(
                cast(population_release_key as string),
                '|',
                cast(planning_area as string)
            )
        )
    ) as population_key
from {{ ref('planning_area_population') }}
