{#
    Component stocks must reconcile within every mart row (bev + phev = plug-in,
    plug-in + non-plug-in = total, conventional hybrids a subset of non-plug-in),
    every published share must lie in [0, 1] and, on complete rows, recompute
    exactly from the row's own stock columns, and every month must carry exactly
    six distinct vehicle scopes. Empty result = pass.
#}

with adoption as (

    select * from {{ ref('mart_national_ev_adoption_monthly') }}

),

component_violations as (

    select
        month_end,
        vehicle_scope,
        'component_mismatch' as violation_reason
    from adoption
    where
        bev_population + phev_population != plug_in_vehicle_population
        or plug_in_vehicle_population + non_plug_in_vehicle_population
        != total_vehicle_population
        or non_plug_in_hybrid_population > non_plug_in_vehicle_population
        or bev_share < 0
        or bev_share > 1
        or phev_share < 0
        or phev_share > 1
        or plug_in_vehicle_share < 0
        or plug_in_vehicle_share > 1
        or (
            adoption_data_status = 'complete'
            and (
                bev_share is distinct from
                safe_divide(bev_population, total_vehicle_population)
                or phev_share is distinct from
                safe_divide(phev_population, total_vehicle_population)
                or plug_in_vehicle_share is distinct from
                safe_divide(
                    plug_in_vehicle_population, total_vehicle_population
                )
            )
        )

),

scope_counts as (

    {#
        Counted before aliasing a NULL vehicle_scope: BigQuery resolves SELECT
        aliases inside HAVING, so counting distinct scopes in the violation
        select itself would count the NULL alias, not the table column.
    #}
    select
        month_end,
        count(*) as month_row_count,
        count(distinct vehicle_scope) as month_scope_count
    from adoption
    group by month_end

),

scope_count_violations as (

    select
        month_end,
        cast(null as string) as vehicle_scope,
        'month_scope_count_not_six' as violation_reason
    from scope_counts
    where month_row_count != 6 or month_scope_count != 6

)

select
    month_end,
    vehicle_scope,
    violation_reason
from component_violations
union all
select
    month_end,
    vehicle_scope,
    violation_reason
from scope_count_violations
