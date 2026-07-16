-- Only complete, publishable cohorts may have scores. Scores, arithmetic, and
-- classification must follow the versioned policy on every scored row.
select *
from {{ ref('mart_supply_demand_gap') }}
where
    (
        score_status = 'scored'
        and (
            demand_index is null
            or supply_index is null
            or mismatch_score is null
            or service_band is null
            or rank_population_size != expected_rank_population_size
            or expected_rank_population_size != 55
        )
    )
    or (
        score_status != 'scored'
        and (
            demand_index is not null
            or supply_index is not null
            or mismatch_score is not null
            or service_band is not null
        )
    )
    or demand_index not between 0 and 1
    or supply_index not between 0 and 1
    or mismatch_score not between -1 and 1
    or abs(mismatch_score - (demand_index - supply_index)) > 1e-9
    or (
        score_status = 'scored'
        and service_band != case
            when mismatch_score >= underserved_threshold then 'underserved'
            when mismatch_score <= overserved_threshold then 'overserved'
            else 'broadly_balanced'
        end
    )
