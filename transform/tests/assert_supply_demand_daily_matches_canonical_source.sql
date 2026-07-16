-- Independently reconstruct canonical source snapshots. Duplicate ingestion
-- batches must contribute once to coverage and connector observations.
with batch_profiles as (

    select
        batch_id,
        any_value(snapshot_date) as snapshot_date,
        any_value(snapshot_time) as snapshot_time,
        max(ingested_at) as ingested_at,
        count(distinct postal_code) as network_location_count,
        sum(total_connectors) as network_connector_count
    from {{ ref('fct_ev_location_availability') }}
    group by batch_id

),

evaluated_batches as (

    select
        batch_profiles.*,
        network_location_count
        >= {{ var('supply_demand_min_network_location_count') }}
        and network_connector_count
        >= {{ var('supply_demand_min_network_connector_count') }}
            as is_qualified,
        case
            when
                network_location_count
                < {{ var('supply_demand_min_network_location_count') }}
                and network_connector_count
                < {{ var('supply_demand_min_network_connector_count') }}
                then 'below_both'
            when
                network_location_count
                < {{ var('supply_demand_min_network_location_count') }}
                then 'below_location'
            when
                network_connector_count
                < {{ var('supply_demand_min_network_connector_count') }}
                then 'below_connector'
        end as rejection_reason
    from batch_profiles

),

ranked_batches as (

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

canonical_batches as (

    select *
    from ranked_batches
    where source_snapshot_rank = 1

),

raw_daily as (

    select
        snapshot_date,
        count(*) as raw_count
    from batch_profiles
    group by snapshot_date

),

expected_daily as (

    select
        canonical_batches.snapshot_date,
        raw_daily.raw_count,
        count(*) as canonical_count,
        countif(canonical_batches.is_qualified) as qualified_count,
        countif(not canonical_batches.is_qualified) as rejected_count,
        countif(canonical_batches.rejection_reason = 'below_both')
            as rejected_below_both_count,
        countif(canonical_batches.rejection_reason = 'below_location')
            as rejected_below_location_count,
        countif(canonical_batches.rejection_reason = 'below_connector')
            as rejected_below_connector_count
    from canonical_batches
    inner join raw_daily
        on canonical_batches.snapshot_date = raw_daily.snapshot_date
    group by canonical_batches.snapshot_date, raw_daily.raw_count

),

actual_daily as (

    select distinct
        snapshot_date,
        observed_daily_ingestion_batch_count,
        duplicate_daily_ingestion_batch_count,
        observed_daily_snapshot_count,
        qualified_daily_snapshot_count,
        rejected_daily_snapshot_count,
        rejected_below_location_and_connector_bounds_snapshot_count,
        rejected_below_location_bound_only_snapshot_count,
        rejected_below_connector_bound_only_snapshot_count
    from {{ ref('fct_supply_demand_daily') }}

),

daily_violations as (

    select
        actual.snapshot_date,
        cast(null as string) as planning_area,
        'daily_snapshot_diagnostics' as violation
    from actual_daily as actual
    inner join expected_daily as expected
        on actual.snapshot_date = expected.snapshot_date
    where
        actual.observed_daily_ingestion_batch_count != expected.raw_count
        or actual.duplicate_daily_ingestion_batch_count
        != expected.raw_count - expected.canonical_count
        or actual.observed_daily_snapshot_count != expected.canonical_count
        or actual.qualified_daily_snapshot_count != expected.qualified_count
        or actual.rejected_daily_snapshot_count != expected.rejected_count
        or actual.rejected_below_location_and_connector_bounds_snapshot_count
        != expected.rejected_below_both_count
        or actual.rejected_below_location_bound_only_snapshot_count
        != expected.rejected_below_location_count
        or actual.rejected_below_connector_bound_only_snapshot_count
        != expected.rejected_below_connector_count

),

expected_area_observations as (

    select
        canonical_batches.snapshot_date,
        availability.planning_area,
        sum(availability.available_connectors) as available_count,
        sum(availability.occupied_connectors) as occupied_count,
        sum(availability.unavailable_connectors) as unavailable_count,
        sum(
            availability.total_connectors
            - availability.available_connectors
            - availability.occupied_connectors
            - availability.unavailable_connectors
        ) as unknown_count,
        sum(availability.total_connectors) as total_count
    from canonical_batches
    inner join {{ ref('fct_ev_location_availability') }} as availability
        on canonical_batches.batch_id = availability.batch_id
    where
        canonical_batches.is_qualified
        and availability.planning_area is not null
    group by canonical_batches.snapshot_date, availability.planning_area

),

area_violations as (

    select
        actual.snapshot_date,
        actual.planning_area,
        'canonical_connector_observations' as violation
    from {{ ref('fct_supply_demand_daily') }} as actual
    left join expected_area_observations as expected
        on
            actual.snapshot_date = expected.snapshot_date
            and actual.planning_area = expected.planning_area
    where
        actual.qualified_daily_snapshot_count > 0
        and (
            actual.available_connectors_observed
            != coalesce(expected.available_count, 0)
            or actual.occupied_connectors_observed
            != coalesce(expected.occupied_count, 0)
            or actual.unavailable_connectors_observed
            != coalesce(expected.unavailable_count, 0)
            or actual.unknown_connectors_observed
            != coalesce(expected.unknown_count, 0)
            or actual.total_connectors_observed
            != coalesce(expected.total_count, 0)
        )

)

select * from daily_violations
union all
select * from area_violations
