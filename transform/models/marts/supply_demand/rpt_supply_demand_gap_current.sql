{{ config(materialized='table', contract={'enforced': true}) }}

with latest_publishable_candidate as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('mart_supply_demand_gap') }}
    where
        daily_data_quality_status = 'publishable'
        and is_complete_day

),

validated_candidate as (

    select latest_publishable_candidate.snapshot_date
    from {{ ref('mart_supply_demand_gap') }} as gap
    inner join latest_publishable_candidate
        on gap.snapshot_date = latest_publishable_candidate.snapshot_date
    group by latest_publishable_candidate.snapshot_date
    having
        count(*) = {{ var('supply_demand_expected_rank_population_size') }}
        and countif(gap.score_status = 'scored')
        = {{ var('supply_demand_expected_rank_population_size') }}
        and countif(
            gap.rank_population_size
            = {{ var('supply_demand_expected_rank_population_size') }}
            and gap.expected_rank_population_size
            = {{ var('supply_demand_expected_rank_population_size') }}
        ) = {{ var('supply_demand_expected_rank_population_size') }}

),

reporting_projection as (

    select
        gap.*,
        format_date('%Y-%m-%d', gap.snapshot_date) as as_of_date_sgt,
        concat(
            'Resident population, ',
            format_date('%B %Y', gap.source_reference_date)
        ) as population_reference,
        concat(
            'Published ',
            format_date('%Y-%m-%d', gap.source_published_date)
        ) as population_publication_reference,
        concat(
            'Retrieved ',
            format_date('%Y-%m-%d', gap.source_retrieved_date)
        ) as population_retrieval_reference
    from {{ ref('mart_supply_demand_gap') }} as gap
    inner join validated_candidate
        on gap.snapshot_date = validated_candidate.snapshot_date

)

select
    as_of_date_sgt,
    planning_area,
    region,
    boundary,
    area_sqkm,
    population_year,
    population_release_key,
    population_reference,
    population_publication_reference,
    population_retrieval_reference,
    planning_geography_version,
    resident_population,
    population_density_per_sqkm,
    population_data_status,
    observed_daily_ingestion_batch_count,
    duplicate_daily_ingestion_batch_count,
    observed_daily_snapshot_count,
    qualified_daily_snapshot_count,
    rejected_daily_snapshot_count,
    rejected_below_location_and_connector_bounds_snapshot_count,
    rejected_below_location_bound_only_snapshot_count,
    rejected_below_connector_bound_only_snapshot_count,
    expected_daily_snapshot_count,
    snapshot_coverage_rate,
    is_complete_day,
    daily_data_quality_status,
    latest_qualified_location_count,
    latest_qualified_connector_count,
    latest_qualified_connector_density_per_sqkm,
    available_connectors_observed,
    occupied_connectors_observed,
    unavailable_connectors_observed,
    unknown_connectors_observed,
    total_connectors_observed,
    average_available_connectors_per_qualified_snapshot,
    effective_available_connectors_per_sqkm,
    daily_availability_rate,
    daily_occupied_rate,
    daily_unavailable_rate,
    daily_unknown_rate,
    supply_demand_daily_key,
    rank_population_size,
    expected_rank_population_size,
    demand_index,
    supply_index,
    mismatch_score,
    service_band,
    score_status,
    score_version,
    underserved_threshold,
    overserved_threshold
from reporting_projection
