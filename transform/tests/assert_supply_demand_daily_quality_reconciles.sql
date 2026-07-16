-- Daily diagnostics are repeated on area rows but must be internally
-- consistent and agree with the approved publishability policy.
with daily_diagnostics as (

    select distinct
        snapshot_date,
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
        daily_data_quality_status
    from {{ ref('fct_supply_demand_daily') }}

)

select *
from daily_diagnostics
where
    expected_daily_snapshot_count <= 0
    or observed_daily_ingestion_batch_count
    != observed_daily_snapshot_count + duplicate_daily_ingestion_batch_count
    or observed_daily_snapshot_count
    != qualified_daily_snapshot_count + rejected_daily_snapshot_count
    or rejected_daily_snapshot_count != (
        rejected_below_location_and_connector_bounds_snapshot_count
        + rejected_below_location_bound_only_snapshot_count
        + rejected_below_connector_bound_only_snapshot_count
    )
    or snapshot_coverage_rate < 0
    or snapshot_coverage_rate > 1
    or abs(
        snapshot_coverage_rate
        - least(
            safe_divide(
                qualified_daily_snapshot_count,
                expected_daily_snapshot_count
            ),
            1.0
        )
    ) > 1e-9
    or (
        qualified_daily_snapshot_count = 0
        and snapshot_coverage_rate != 0.0
    )
    or is_complete_day != (
        snapshot_date < current_date('Asia/Singapore')
        and qualified_daily_snapshot_count > 0
        and snapshot_coverage_rate
        >= {{ var('supply_demand_min_daily_snapshot_coverage') }}
    )
    or daily_data_quality_status != case
        when snapshot_date = current_date('Asia/Singapore') then 'open_day'
        when
            qualified_daily_snapshot_count > 0
            and snapshot_coverage_rate
            >= {{ var('supply_demand_min_daily_snapshot_coverage') }}
            then 'publishable'
        else 'insufficient_snapshot_coverage'
    end
