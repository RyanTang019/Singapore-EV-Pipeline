{% set supplied_as_of_date = var('supply_demand_as_of_date', none) %}

{{
    config(
        materialized='table',
        partition_by={
            'field': 'snapshot_date',
            'data_type': 'date',
            'granularity': 'day'
        },
        cluster_by=['planning_area']
    )
}}

with parameters as (

    select
        cast({{ var('supply_demand_expected_daily_snapshot_count') }} as int64)
            as expected_daily_snapshot_count,
        cast({{ var('supply_demand_min_daily_snapshot_coverage') }} as float64)
            as min_daily_snapshot_coverage,
        cast({{ var('supply_demand_min_network_location_count') }} as int64)
            as min_network_location_count,
        cast({{ var('supply_demand_min_network_connector_count') }} as int64)
            as min_network_connector_count,
        {% if supplied_as_of_date is not none %}
            cast('{{ supplied_as_of_date }}' as date) as effective_current_date
        {% else %}
            current_date('Asia/Singapore') as effective_current_date
        {% endif %}

),

batch_profiles as (

    select
        batch_id,
        any_value(snapshot_date) as snapshot_date,
        any_value(snapshot_time) as snapshot_time,
        max(ingested_at) as ingested_at,
        count(distinct snapshot_time) as source_snapshot_time_count,
        countif(snapshot_time is null) as null_snapshot_time_row_count,
        count(distinct snapshot_date) as snapshot_date_count,
        count(distinct postal_code) as network_location_count,
        sum(total_connectors) as network_connector_count,
        sum(available_connectors) as network_available_connector_count,
        sum(occupied_connectors) as network_occupied_connector_count,
        sum(unavailable_connectors) as network_unavailable_connector_count,
        sum(
            total_connectors
            - available_connectors
            - occupied_connectors
            - unavailable_connectors
        ) as network_unknown_connector_count
    from {{ ref('fct_ev_location_availability') }}
    group by batch_id

),

evaluated_batches as (

    select
        batch_profiles.*,
        batch_profiles.network_location_count
        >= parameters.min_network_location_count
        and batch_profiles.network_connector_count
        >= parameters.min_network_connector_count
            as is_qualified,
        case
            when
                batch_profiles.network_location_count
                < parameters.min_network_location_count
                and batch_profiles.network_connector_count
                < parameters.min_network_connector_count
                then 'below_location_and_connector_bounds'
            when
                batch_profiles.network_location_count
                < parameters.min_network_location_count
                then 'below_location_bound'
            when
                batch_profiles.network_connector_count
                < parameters.min_network_connector_count
                then 'below_connector_bound'
        end as rejection_reason
    from batch_profiles
    cross join parameters

),

ranked_source_snapshots as (

    select
        evaluated_batches.*,
        row_number() over (
            partition by snapshot_time
            order by
                is_qualified desc,
                network_connector_count desc,
                network_location_count desc,
                ingested_at desc,
                batch_id desc
        ) as source_snapshot_rank
    from evaluated_batches

),

canonical_source_snapshots as (

    select
        batch_id,
        snapshot_date,
        snapshot_time,
        ingested_at,
        network_location_count,
        network_connector_count,
        is_qualified,
        rejection_reason
    from ranked_source_snapshots
    where source_snapshot_rank = 1

),

calendar_bounds as (

    select
        parameters.effective_current_date,
        min(batch_profiles.snapshot_date) as first_snapshot_date
    from batch_profiles
    cross join parameters
    group by parameters.effective_current_date

),

date_spine as (

    select snapshot_date
    from calendar_bounds
    cross join unnest(
        generate_date_array(first_snapshot_date, effective_current_date)
    ) as snapshot_date

),

daily_spine as (

    select
        date_spine.snapshot_date,
        planning_areas.planning_area,
        planning_areas.region,
        planning_areas.boundary,
        planning_areas.area_sqkm
    from date_spine
    cross join {{ ref('dim_planning_area') }} as planning_areas

),

raw_daily_diagnostics as (

    select
        snapshot_date,
        count(*) as observed_daily_ingestion_batch_count
    from batch_profiles
    group by snapshot_date

),

canonical_daily_diagnostics as (

    select
        snapshot_date,
        count(*) as observed_daily_snapshot_count,
        countif(is_qualified) as qualified_daily_snapshot_count,
        countif(not is_qualified) as rejected_daily_snapshot_count,
        countif(rejection_reason = 'below_location_and_connector_bounds')
            as rejected_below_both_count,
        countif(rejection_reason = 'below_location_bound')
            as rejected_below_location_count,
        countif(rejection_reason = 'below_connector_bound')
            as rejected_below_connector_count
    from canonical_source_snapshots
    group by snapshot_date

),

latest_qualified_source_snapshots as (

    select
        snapshot_date,
        batch_id
    from canonical_source_snapshots
    where is_qualified
    qualify row_number() over (
        partition by snapshot_date
        order by snapshot_time desc, ingested_at desc, batch_id desc
    ) = 1

),

daily_diagnostics as (

    select
        date_spine.snapshot_date,
        parameters.expected_daily_snapshot_count,
        parameters.min_daily_snapshot_coverage,
        parameters.effective_current_date,
        coalesce(
            raw_daily_diagnostics.observed_daily_ingestion_batch_count,
            0
        ) as observed_daily_ingestion_batch_count,
        coalesce(
            raw_daily_diagnostics.observed_daily_ingestion_batch_count,
            0
        ) - coalesce(
            canonical.observed_daily_snapshot_count,
            0
        ) as duplicate_daily_ingestion_batch_count,
        coalesce(
            canonical.observed_daily_snapshot_count,
            0
        ) as observed_daily_snapshot_count,
        coalesce(
            canonical.qualified_daily_snapshot_count,
            0
        ) as qualified_daily_snapshot_count,
        coalesce(
            canonical.rejected_daily_snapshot_count,
            0
        ) as rejected_daily_snapshot_count,
        coalesce(
            canonical.rejected_below_both_count,
            0
        ) as rejected_below_location_and_connector_bounds_snapshot_count,
        coalesce(
            canonical.rejected_below_location_count,
            0
        ) as rejected_below_location_bound_only_snapshot_count,
        coalesce(
            canonical.rejected_below_connector_count,
            0
        ) as rejected_below_connector_bound_only_snapshot_count,
        least(
            safe_divide(
                coalesce(
                    canonical.qualified_daily_snapshot_count,
                    0
                ),
                parameters.expected_daily_snapshot_count
            ),
            1.0
        ) as snapshot_coverage_rate
    from date_spine
    cross join parameters
    left join raw_daily_diagnostics
        on date_spine.snapshot_date = raw_daily_diagnostics.snapshot_date
    left join canonical_daily_diagnostics as canonical
        on date_spine.snapshot_date = canonical.snapshot_date

),

qualified_area_observations as (

    select
        canonical_source_snapshots.snapshot_date,
        availability.planning_area,
        sum(availability.available_connectors) as available_connectors_observed,
        sum(availability.occupied_connectors) as occupied_connectors_observed,
        sum(availability.unavailable_connectors)
            as unavailable_connectors_observed,
        sum(
            availability.total_connectors
            - availability.available_connectors
            - availability.occupied_connectors
            - availability.unavailable_connectors
        ) as unknown_connectors_observed,
        sum(availability.total_connectors) as total_connectors_observed
    from canonical_source_snapshots
    inner join
        {{ ref('fct_ev_location_availability') }} as availability
        on canonical_source_snapshots.batch_id = availability.batch_id
    where
        canonical_source_snapshots.is_qualified
        and availability.planning_area is not null
    group by
        canonical_source_snapshots.snapshot_date, availability.planning_area

),

latest_qualified_area_capacity as (

    select
        latest_snapshots.snapshot_date,
        availability.planning_area,
        count(distinct availability.postal_code)
            as latest_qualified_location_count,
        sum(availability.total_connectors) as latest_qualified_connector_count
    from latest_qualified_source_snapshots as latest_snapshots
    inner join
        {{ ref('fct_ev_location_availability') }} as availability
        on latest_snapshots.batch_id = availability.batch_id
    where availability.planning_area is not null
    group by latest_snapshots.snapshot_date, availability.planning_area

),

population_release_metadata as (

    select distinct
        population_year,
        population_release_key,
        source_reference_date,
        source_published_date,
        source_retrieved_date,
        planning_geography_version
    from {{ ref('fct_planning_area_population') }}

),

date_population_release as (

    select
        date_spine.snapshot_date,
        population_release_metadata.population_year,
        population_release_metadata.population_release_key,
        population_release_metadata.source_reference_date,
        population_release_metadata.source_published_date,
        population_release_metadata.source_retrieved_date,
        population_release_metadata.planning_geography_version
    from date_spine
    left join population_release_metadata
        on
            date_spine.snapshot_date
            >= population_release_metadata.source_reference_date
    qualify row_number() over (
        partition by date_spine.snapshot_date
        order by
            population_release_metadata.source_reference_date desc,
            population_release_metadata.source_published_date desc,
            population_release_metadata.source_retrieved_date desc,
            population_release_metadata.population_release_key desc
    ) = 1

),

daily_inputs as (

    select
        daily_spine.snapshot_date,
        daily_spine.planning_area,
        daily_spine.region,
        daily_spine.boundary,
        daily_spine.area_sqkm,
        date_population_release.population_year,
        date_population_release.population_release_key,
        date_population_release.source_reference_date,
        date_population_release.source_published_date,
        date_population_release.source_retrieved_date,
        date_population_release.planning_geography_version,
        population.resident_population,
        population.population_density_per_sqkm,
        population.population_data_status,
        diagnostics.observed_daily_ingestion_batch_count,
        diagnostics.duplicate_daily_ingestion_batch_count,
        diagnostics.observed_daily_snapshot_count,
        diagnostics.qualified_daily_snapshot_count,
        diagnostics.rejected_daily_snapshot_count,
        diagnostics.rejected_below_location_and_connector_bounds_snapshot_count,
        diagnostics.rejected_below_location_bound_only_snapshot_count,
        diagnostics.rejected_below_connector_bound_only_snapshot_count,
        diagnostics.expected_daily_snapshot_count,
        diagnostics.snapshot_coverage_rate,
        diagnostics.min_daily_snapshot_coverage,
        diagnostics.effective_current_date,
        qualified_area_observations.available_connectors_observed,
        qualified_area_observations.occupied_connectors_observed,
        qualified_area_observations.unavailable_connectors_observed,
        qualified_area_observations.unknown_connectors_observed,
        qualified_area_observations.total_connectors_observed,
        latest_qualified_area_capacity.latest_qualified_location_count,
        latest_qualified_area_capacity.latest_qualified_connector_count
    from daily_spine
    inner join
        daily_diagnostics as diagnostics
        on daily_spine.snapshot_date = diagnostics.snapshot_date
    inner join date_population_release
        on daily_spine.snapshot_date = date_population_release.snapshot_date
    left join {{ ref('fct_planning_area_population') }} as population
        on
            date_population_release.population_release_key
            = population.population_release_key
            and daily_spine.planning_area = population.planning_area
    left join qualified_area_observations
        on
            daily_spine.snapshot_date
            = qualified_area_observations.snapshot_date
            and daily_spine.planning_area
            = qualified_area_observations.planning_area
    left join latest_qualified_area_capacity
        on
            daily_spine.snapshot_date
            = latest_qualified_area_capacity.snapshot_date
            and daily_spine.planning_area
            = latest_qualified_area_capacity.planning_area

),

daily_measures as (

    select
        daily_inputs.* except (
            min_daily_snapshot_coverage,
            effective_current_date,
            available_connectors_observed,
            occupied_connectors_observed,
            unavailable_connectors_observed,
            unknown_connectors_observed,
            total_connectors_observed,
            latest_qualified_location_count,
            latest_qualified_connector_count
        ),
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(latest_qualified_location_count, 0)
        end as latest_qualified_location_count,
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(latest_qualified_connector_count, 0)
        end as latest_qualified_connector_count,
        case
            when qualified_daily_snapshot_count > 0
                then
                    safe_divide(
                        coalesce(latest_qualified_connector_count, 0), area_sqkm
                    )
        end as latest_qualified_connector_density_per_sqkm,
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(available_connectors_observed, 0)
        end as available_connectors_observed,
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(occupied_connectors_observed, 0)
        end as occupied_connectors_observed,
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(unavailable_connectors_observed, 0)
        end as unavailable_connectors_observed,
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(unknown_connectors_observed, 0)
        end as unknown_connectors_observed,
        case
            when qualified_daily_snapshot_count > 0
                then coalesce(total_connectors_observed, 0)
        end as total_connectors_observed,
        case
            when qualified_daily_snapshot_count > 0
                then safe_divide(
                    coalesce(available_connectors_observed, 0),
                    qualified_daily_snapshot_count
                )
        end as average_available_connectors_per_qualified_snapshot,
        case
            when qualified_daily_snapshot_count > 0
                then
                    safe_divide(
                        coalesce(available_connectors_observed, 0), area_sqkm
                    )
                    / qualified_daily_snapshot_count
        end as effective_available_connectors_per_sqkm,
        case
            when qualified_daily_snapshot_count > 0
                then
                    safe_divide(
                        available_connectors_observed, total_connectors_observed
                    )
        end as daily_availability_rate,
        case
            when qualified_daily_snapshot_count > 0
                then
                    safe_divide(
                        occupied_connectors_observed, total_connectors_observed
                    )
        end as daily_occupied_rate,
        case
            when qualified_daily_snapshot_count > 0
                then
                    safe_divide(
                        unavailable_connectors_observed,
                        total_connectors_observed
                    )
        end as daily_unavailable_rate,
        case
            when qualified_daily_snapshot_count > 0
                then
                    safe_divide(
                        unknown_connectors_observed, total_connectors_observed
                    )
        end as daily_unknown_rate,
        snapshot_date < effective_current_date
        and qualified_daily_snapshot_count > 0
        and snapshot_coverage_rate
        >= min_daily_snapshot_coverage as is_complete_day,
        case
            when snapshot_date = effective_current_date then 'open_day'
            when
                qualified_daily_snapshot_count > 0
                and snapshot_coverage_rate >= min_daily_snapshot_coverage
                then 'publishable'
            else 'insufficient_snapshot_coverage'
        end as daily_data_quality_status
    from daily_inputs

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
    to_hex(
        md5(
            concat(
                cast(snapshot_date as string),
                '|',
                planning_area
            )
        )
    ) as supply_demand_daily_key
from daily_measures
