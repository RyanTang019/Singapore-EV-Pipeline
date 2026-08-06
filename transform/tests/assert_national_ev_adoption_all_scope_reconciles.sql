{#
    The all_vehicles rollup row must equal the sum of the five vehicle-category
    rows for every stock measure in every month. IS DISTINCT FROM catches a NULL
    on either side as loudly as a numeric mismatch, and the full outer join
    catches a month missing its rollup row entirely. Empty result = pass.
#}

with adoption as (

    select * from {{ ref('mart_national_ev_adoption_monthly') }}

),

category_sums as (

    select
        month_end,
        sum(total_vehicle_population) as total_vehicle_population,
        sum(bev_population) as bev_population,
        sum(phev_population) as phev_population,
        sum(plug_in_vehicle_population) as plug_in_vehicle_population,
        sum(non_plug_in_vehicle_population) as non_plug_in_vehicle_population,
        sum(non_plug_in_hybrid_population) as non_plug_in_hybrid_population
    from adoption
    where vehicle_scope != 'all_vehicles'
    group by month_end

),

rollup_rows as (

    select
        month_end,
        total_vehicle_population,
        bev_population,
        phev_population,
        plug_in_vehicle_population,
        non_plug_in_vehicle_population,
        non_plug_in_hybrid_population
    from adoption
    where vehicle_scope = 'all_vehicles'

)

select
    category_sums.month_end as category_month_end,
    rollup_rows.month_end as rollup_month_end,
    category_sums.total_vehicle_population as category_total,
    rollup_rows.total_vehicle_population as rollup_total
from category_sums
full outer join rollup_rows
    on category_sums.month_end = rollup_rows.month_end
where
    category_sums.month_end is null
    or rollup_rows.month_end is null
    or rollup_rows.total_vehicle_population
    is distinct from category_sums.total_vehicle_population
    or rollup_rows.bev_population
    is distinct from category_sums.bev_population
    or rollup_rows.phev_population
    is distinct from category_sums.phev_population
    or rollup_rows.plug_in_vehicle_population
    is distinct from category_sums.plug_in_vehicle_population
    or rollup_rows.non_plug_in_vehicle_population
    is distinct from category_sums.non_plug_in_vehicle_population
    or rollup_rows.non_plug_in_hybrid_population
    is distinct from category_sums.non_plug_in_hybrid_population
