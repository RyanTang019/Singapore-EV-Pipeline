-- The versioned production rank cohort is exactly all 55 MP2019 areas.
select
    snapshot_date,
    count(*) as row_count,
    count(distinct planning_area) as planning_area_count
from {{ ref('mart_supply_demand_gap') }}
group by snapshot_date
having
    count(*) != {{ var('supply_demand_expected_rank_population_size') }}
    or count(distinct planning_area)
    != {{ var('supply_demand_expected_rank_population_size') }}
