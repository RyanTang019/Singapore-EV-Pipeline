{#
    V1 retains exactly one controlled source vintage: one release-metadata row and one distinct
    observation release key, and the two must be the same key. The release row also describes its
    own extent, so every self-described count and date bound is recomputed from the staged
    observations rather than trusted. Empty result = pass.
#}

with release_metadata as (

    select
        count(*) as metadata_row_count,
        count(distinct source_release_key) as release_key_count,
        min(source_release_key) as release_key,
        min(source_row_count) as source_row_count,
        min(first_month_end) as first_month_end,
        min(latest_month_end) as latest_month_end,
        min(source_vehicle_category_count) as category_count,
        min(source_fuel_type_count) as fuel_type_count
    from {{ ref('stg_lta_monthly_vehicle_population_releases') }}

),

staged_observations as (

    select
        count(*) as source_row_count,
        count(distinct source_release_key) as release_key_count,
        min(source_release_key) as release_key,
        min(month_end) as first_month_end,
        max(month_end) as latest_month_end,
        count(distinct source_vehicle_category) as category_count,
        count(distinct source_fuel_type) as fuel_type_count
    from {{ ref('stg_lta_monthly_vehicle_population_by_fuel') }}

)

select
    releases.release_key as metadata_release_key,
    observed.release_key as observation_release_key,
    releases.source_row_count as declared_row_count,
    observed.source_row_count as observed_row_count
from release_metadata as releases
cross join staged_observations as observed
where
    releases.metadata_row_count != 1
    or releases.release_key_count != 1
    or observed.release_key_count != 1
    or releases.release_key != observed.release_key
    or releases.source_row_count != observed.source_row_count
    or releases.first_month_end != observed.first_month_end
    or releases.latest_month_end != observed.latest_month_end
    or releases.category_count != observed.category_count
    or releases.fuel_type_count != observed.fuel_type_count
