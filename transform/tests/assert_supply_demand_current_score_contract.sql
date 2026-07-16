-- The reporting slice is fully scored and single-valued on version policy.
select *
from {{ ref('rpt_supply_demand_gap_current') }}
where
    score_status != 'scored'
    or daily_data_quality_status != 'publishable'
    or not is_complete_day
    or rank_population_size != 55
    or expected_rank_population_size != 55
    or score_version != 'population_gap_v1'
    or underserved_threshold != 0.25
    or overserved_threshold != -0.25
    or demand_index is null
    or demand_index not between 0 and 1
    or supply_index is null
    or supply_index not between 0 and 1
    or mismatch_score is null
    or mismatch_score not between -1 and 1
    or service_band is null
    or population_reference is null
    or population_publication_reference is null
    or population_retrieval_reference is null
