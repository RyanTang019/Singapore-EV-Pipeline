{{ config(materialized='table') }}

{#
    National registered-vehicle stock at month_end x vehicle_type x source_fuel_type for the
    single active LTA M09 release. Every published fuel row is retained, not just plug-in rows:
    non-plug-in stock is the denominator for every downstream share. Classification is an inner
    join on the exact source fuel label, so an unmapped label drops rows loudly (caught by
    assert_national_ev_adoption_classification_valid) rather than being null-filled. The fact key
    deliberately omits the release key because staging enforces exactly one active release.
#}

with observations as (

    select
        source_release_key,
        month_end,
        source_vehicle_category,
        vehicle_type,
        source_fuel_type,
        source_value_token,
        vehicle_population,
        source_value_status
    from {{ ref('stg_lta_monthly_vehicle_population_by_fuel') }}

),

releases as (

    select
        source_release_key,
        source_dataset_id,
        source_retrieved_date,
        latest_month_end,
        csv_sha256
    from {{ ref('stg_lta_monthly_vehicle_population_releases') }}

),

classification as (

    select
        source_fuel_type,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version
    from {{ ref('lta_fuel_type_classification') }}

),

classified_observations as (

    select
        observations.month_end,
        observations.vehicle_type,
        observations.source_fuel_type,
        observations.source_vehicle_category,
        observations.source_value_token,
        observations.source_value_status,
        observations.vehicle_population,
        classification.powertrain_group,
        classification.is_bev,
        classification.is_phev,
        classification.is_plug_in_vehicle,
        classification.classification_version,
        releases.source_release_key,
        releases.source_dataset_id,
        releases.source_retrieved_date,
        releases.csv_sha256,
        releases.latest_month_end as latest_source_month_end,
        to_hex(
            md5(
                concat(
                    cast(observations.month_end as string),
                    '|',
                    observations.vehicle_type,
                    '|',
                    observations.source_fuel_type
                )
            )
        ) as adoption_fact_key
    from observations
    inner join classification
        on observations.source_fuel_type = classification.source_fuel_type
    inner join releases
        on observations.source_release_key = releases.source_release_key

)

select
    adoption_fact_key,
    source_release_key,
    source_dataset_id,
    month_end,
    vehicle_type,
    source_fuel_type,
    source_vehicle_category,
    source_value_token,
    source_value_status,
    powertrain_group,
    classification_version,
    csv_sha256,
    vehicle_population,
    is_bev,
    is_phev,
    is_plug_in_vehicle,
    source_retrieved_date,
    latest_source_month_end
from classified_observations
