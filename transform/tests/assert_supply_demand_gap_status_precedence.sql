-- Daily quality wins first, followed by release/population exceptions and the
-- fail-closed fixed-cohort gate.
select *
from {{ ref('mart_supply_demand_gap') }}
where score_status != case
    when daily_data_quality_status != 'publishable'
        then 'daily_data_not_publishable'
    when population_release_key is null
        then 'no_population_snapshot_as_of_date'
    when population_data_status = 'missing'
        then 'missing_population'
    when rank_population_size != expected_rank_population_size
        then 'incomplete_rank_cohort'
    else 'scored'
end
