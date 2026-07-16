-- Cohort diagnostics and population_gap_v1 parameters are version policy,
-- not values that may vary by date or area.
with cohort_sizes as (

    select
        snapshot_date,
        countif(
            population_data_status in ('reported', 'reported_zero')
        ) as actual_rank_population_size
    from {{ ref('mart_supply_demand_gap') }}
    group by snapshot_date

)

select
    gap.snapshot_date,
    gap.planning_area,
    gap.rank_population_size,
    cohort_sizes.actual_rank_population_size,
    gap.expected_rank_population_size,
    gap.score_version,
    gap.underserved_threshold,
    gap.overserved_threshold
from {{ ref('mart_supply_demand_gap') }} as gap
inner join cohort_sizes
    on gap.snapshot_date = cohort_sizes.snapshot_date
where
    gap.rank_population_size != cohort_sizes.actual_rank_population_size
    or gap.expected_rank_population_size != 55
    or gap.expected_rank_population_size
    != {{ var('supply_demand_expected_rank_population_size') }}
    or gap.score_version != 'population_gap_v1'
    or gap.underserved_threshold != 0.25
    or gap.overserved_threshold != -0.25
