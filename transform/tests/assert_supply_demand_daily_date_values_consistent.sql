-- Daily diagnostics and selected population provenance must not vary across
-- the 55 planning-area rows for a date.
select
    snapshot_date,
    count(*) as row_count
from {{ ref('fct_supply_demand_daily') }}
group by snapshot_date
having
    count(distinct observed_daily_ingestion_batch_count) != 1
    or count(distinct duplicate_daily_ingestion_batch_count) != 1
    or count(distinct observed_daily_snapshot_count) != 1
    or count(distinct qualified_daily_snapshot_count) != 1
    or count(distinct rejected_daily_snapshot_count) != 1
    or count(
        distinct rejected_below_location_and_connector_bounds_snapshot_count
    ) != 1
    or count(
        distinct rejected_below_location_bound_only_snapshot_count
    ) != 1
    or count(
        distinct rejected_below_connector_bound_only_snapshot_count
    ) != 1
    or count(distinct expected_daily_snapshot_count) != 1
    or count(distinct snapshot_coverage_rate) != 1
    or count(distinct is_complete_day) != 1
    or count(distinct daily_data_quality_status) != 1
    or count(distinct coalesce(population_release_key, '__NULL__')) != 1
    or count(
        distinct coalesce(cast(population_year as string), '__NULL__')
    ) != 1
    or count(
        distinct coalesce(cast(source_reference_date as string), '__NULL__')
    ) != 1
