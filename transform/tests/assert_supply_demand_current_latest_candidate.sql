-- The report must use the latest completed supply-publishable candidate and
-- may not fall back to an older scored date.
with latest_candidate as (

    select max(snapshot_date) as snapshot_date
    from {{ ref('mart_supply_demand_gap') }}
    where
        daily_data_quality_status = 'publishable'
        and is_complete_day

),

report_summary as (

    select
        count(*) as row_count,
        count(distinct as_of_date_sgt) as as_of_date_count,
        any_value(as_of_date_sgt) as as_of_date_sgt,
        countif(score_status = 'scored') as scored_row_count,
        countif(daily_data_quality_status = 'publishable')
            as publishable_row_count
    from {{ ref('rpt_supply_demand_gap_current') }}

)

select
    report_summary.*,
    latest_candidate.snapshot_date
from latest_candidate
cross join report_summary
where
    report_summary.row_count
    != {{ var('supply_demand_expected_rank_population_size') }}
    or report_summary.as_of_date_count != 1
    or report_summary.as_of_date_sgt
    != format_date('%Y-%m-%d', latest_candidate.snapshot_date)
    or report_summary.scored_row_count
    != {{ var('supply_demand_expected_rank_population_size') }}
    or report_summary.publishable_row_count
    != {{ var('supply_demand_expected_rank_population_size') }}
