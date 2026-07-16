-- Non-negative supply makes raw zero the tied-lowest value; every scored zero
-- must therefore receive PERCENT_RANK zero.
select
    snapshot_date,
    planning_area,
    effective_available_connectors_per_sqkm,
    supply_index
from {{ ref('mart_supply_demand_gap') }}
where
    score_status = 'scored'
    and effective_available_connectors_per_sqkm = 0
    and supply_index != 0
