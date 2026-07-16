-- Every SGT date from the first EV observation through today must contain all
-- 55 MP2019 planning areas, including dates with no represented source batch.
with source_bounds as (

    select min(snapshot_date) as first_snapshot_date
    from {{ ref('fct_ev_location_availability') }}

),

expected_dates as (

    select generated_date as snapshot_date
    from source_bounds
    cross join unnest(
        generate_date_array(
            source_bounds.first_snapshot_date,
            current_date('Asia/Singapore')
        )
    ) as generated_date

),

actual_dates as (

    select
        snapshot_date,
        count(*) as row_count,
        count(distinct planning_area) as planning_area_count
    from {{ ref('fct_supply_demand_daily') }}
    group by snapshot_date

)

select
    actual_dates.row_count,
    actual_dates.planning_area_count,
    coalesce(expected_dates.snapshot_date, actual_dates.snapshot_date)
        as snapshot_date
from expected_dates
full outer join actual_dates
    on expected_dates.snapshot_date = actual_dates.snapshot_date
where
    expected_dates.snapshot_date is null
    or actual_dates.snapshot_date is null
    or actual_dates.row_count
    != {{ var('supply_demand_expected_rank_population_size') }}
    or actual_dates.planning_area_count
    != {{ var('supply_demand_expected_rank_population_size') }}
