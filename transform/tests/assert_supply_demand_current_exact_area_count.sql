-- Zero rows deliberately fail: the reporting boundary publishes only a full
-- 55-area scored slice.
select
    count(*) as row_count,
    count(distinct planning_area) as planning_area_count
from {{ ref('rpt_supply_demand_gap_current') }}
having
    count(*) != {{ var('supply_demand_expected_rank_population_size') }}
    or count(distinct planning_area)
    != {{ var('supply_demand_expected_rank_population_size') }}
