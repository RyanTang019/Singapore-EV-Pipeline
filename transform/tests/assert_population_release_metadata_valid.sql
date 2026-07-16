with approved_source as (

    select
        'singstat_c020125_resident_population_planning_area_subzone_dwelling'
            as source_dataset_id

)

select releases.population_release_key
from {{ ref('stg_planning_area_population_releases') }} as releases
cross join approved_source
where
    releases.source_reference_date > releases.source_published_date
    or releases.source_published_date > releases.source_retrieved_date
    or releases.expected_planning_area_row_count != 55
    or releases.national_resident_population <= 0
    or releases.generated_planning_area_population_total <= 0
    or releases.max_national_reconciliation_difference < 0
    or releases.source_dataset_id != approved_source.source_dataset_id
    or not regexp_contains(releases.source_dataset_id, r'^[a-z0-9_]+$')
    or not regexp_contains(releases.population_release_key, r'^[a-f0-9]{64}$')
    or not regexp_contains(releases.source_sha256, r'^[a-f0-9]{64}$')
    or trim(releases.source_name) = ''
    or trim(releases.source_url) = ''
    or trim(releases.source_filename) = ''
