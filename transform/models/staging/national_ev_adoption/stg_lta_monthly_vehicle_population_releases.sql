{{ config(materialized='view') }}

{#
    Explicitly typed view over the single approved LTA M09 release-metadata row. Exposes source
    identity, retrieval provenance, and the release's self-described counts and date bounds; the
    singular release-integrity test reconciles those against the staged observations.
#}

select
    cast(source_release_key as string) as source_release_key,
    cast(source_dataset_id as string) as source_dataset_id,
    cast(source_name as string) as source_name,
    cast(source_url as string) as source_url,
    cast(source_catalog_update_month as string)
        as source_catalog_update_month,
    cast(source_retrieved_date as date) as source_retrieved_date,
    cast(first_month_end as date) as first_month_end,
    cast(latest_month_end as date) as latest_month_end,
    cast(source_row_count as int64) as source_row_count,
    cast(source_vehicle_category_count as int64)
        as source_vehicle_category_count,
    cast(source_fuel_type_count as int64) as source_fuel_type_count,
    cast(archive_filename as string) as archive_filename,
    cast(archive_sha256 as string) as archive_sha256,
    cast(csv_filename as string) as csv_filename,
    cast(csv_sha256 as string) as csv_sha256
from {{ ref('lta_monthly_vehicle_population_releases') }}
