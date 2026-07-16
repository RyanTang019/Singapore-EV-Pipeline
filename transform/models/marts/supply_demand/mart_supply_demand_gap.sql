{{
    config(
        materialized='table',
        partition_by={
            'field': 'snapshot_date',
            'data_type': 'date',
            'granularity': 'day'
        },
        cluster_by=['planning_area'],
        contract={'enforced': true}
    )
}}

with scoring_policy as (

    select
        'population_gap_v1' as score_version,
        cast(0.25 as float64) as underserved_threshold,
        cast(-0.25 as float64) as overserved_threshold,
        cast(
            {{ var('supply_demand_expected_rank_population_size') }} as int64
        ) as expected_rank_population_size

),

daily_with_cohort as (

    select
        daily.*,
        scoring_policy.expected_rank_population_size,
        scoring_policy.score_version,
        scoring_policy.underserved_threshold,
        scoring_policy.overserved_threshold,
        countif(
            daily.population_data_status in ('reported', 'reported_zero')
        ) over (
            partition by daily.snapshot_date
        ) as rank_population_size
    from {{ ref('fct_supply_demand_daily') }} as daily
    cross join scoring_policy

),

status_assigned as (

    select
        daily_with_cohort.*,
        case
            when daily_data_quality_status != 'publishable'
                then 'daily_data_not_publishable'
            when population_release_key is null
                then 'no_population_snapshot_as_of_date'
            when population_data_status = 'missing'
                then 'missing_population'
            when rank_population_size != expected_rank_population_size
                then 'incomplete_rank_cohort'
            else 'scored'
        end as score_status
    from daily_with_cohort

),

scored_rows as (

    select
        status_assigned.*,
        percent_rank() over (
            partition by snapshot_date
            order by population_density_per_sqkm
        ) as demand_index,
        percent_rank() over (
            partition by snapshot_date
            order by effective_available_connectors_per_sqkm
        ) as supply_index
    from status_assigned
    where score_status = 'scored'

),

non_scored_rows as (

    select
        status_assigned.*,
        cast(null as float64) as demand_index,
        cast(null as float64) as supply_index
    from status_assigned
    where score_status != 'scored'

),

all_rows as (

    select * from scored_rows
    union all
    select * from non_scored_rows

),

rows_with_mismatch as (

    select
        all_rows.*,
        demand_index - supply_index as mismatch_score
    from all_rows

),

rows_with_band as (

    select
        rows_with_mismatch.*,
        case
            when mismatch_score >= underserved_threshold then 'underserved'
            when mismatch_score <= overserved_threshold then 'overserved'
            when score_status = 'scored' then 'broadly_balanced'
        end as service_band
    from rows_with_mismatch

)

select
    snapshot_date,
    planning_area,
    region,
    boundary,
    area_sqkm,
    population_year,
    population_release_key,
    source_reference_date,
    source_published_date,
    source_retrieved_date,
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
from rows_with_band
