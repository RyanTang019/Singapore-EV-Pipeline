{{ config(materialized='view') }}

select
    cast(population_release_key as string) as population_release_key,
    cast(population_year as int64) as population_year,
    cast(source_reference_date as date) as source_reference_date,
    cast(source_published_date as date) as source_published_date,
    cast(source_retrieved_date as date) as source_retrieved_date,
    cast(planning_geography_version as string) as planning_geography_version,
    cast(national_resident_population as int64) as national_resident_population,
    cast(max_national_reconciliation_difference as int64)
        as max_national_reconciliation_difference,
    cast(expected_planning_area_row_count as int64)
        as expected_planning_area_row_count,
    cast(generated_planning_area_population_total as int64)
        as generated_planning_area_population_total,
    cast(source_dataset_id as string) as source_dataset_id,
    cast(source_name as string) as source_name,
    cast(source_url as string) as source_url,
    cast(source_filename as string) as source_filename,
    cast(source_sha256 as string) as source_sha256
from {{ ref('planning_area_population_releases') }}
