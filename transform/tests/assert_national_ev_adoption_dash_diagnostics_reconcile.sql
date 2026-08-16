{#
    Mart dash-row diagnostics must reconcile exactly to direct counts of fact
    source_dash_zero rows per month and scope: the own-month total/BEV/PHEV
    counts against the fact, and all six MoM/YoY comparison counts against the
    fact-derived counts of the comparison month located with the same
    month-safe LAST_DAY(DATE_SUB(DATE_TRUNC(...))) expressions the growth test
    uses. A comparison count must be NULL exactly when the mart has no
    comparison row, and 0 when the comparison row exists without dash rows.
    Empty result = pass.
#}

with adoption as (

    select * from {{ ref('mart_national_ev_adoption_monthly') }}

),

fact_rows as (

    select
        month_end,
        vehicle_type,
        source_value_status,
        is_bev,
        is_phev
    from {{ ref('fct_national_ev_adoption_monthly') }}

),

fact_dash_counts as (

    select
        month_end,
        vehicle_type as vehicle_scope,
        countif(source_value_status = 'source_dash_zero') as dash_row_count,
        countif(
            source_value_status = 'source_dash_zero' and is_bev
        ) as bev_dash_row_count,
        countif(
            source_value_status = 'source_dash_zero' and is_phev
        ) as phev_dash_row_count
    from fact_rows
    group by month_end, vehicle_type
    union all
    select
        month_end,
        'all_vehicles' as vehicle_scope,
        countif(source_value_status = 'source_dash_zero') as dash_row_count,
        countif(
            source_value_status = 'source_dash_zero' and is_bev
        ) as bev_dash_row_count,
        countif(
            source_value_status = 'source_dash_zero' and is_phev
        ) as phev_dash_row_count
    from fact_rows
    group by month_end

),

own_month_violations as (

    select
        adoption.month_end,
        adoption.vehicle_scope,
        'own_month_dash_mismatch' as violation_reason
    from adoption
    left join fact_dash_counts
        on
            adoption.month_end = fact_dash_counts.month_end
            and adoption.vehicle_scope = fact_dash_counts.vehicle_scope
    where
        adoption.source_dash_row_count
        is distinct from coalesce(fact_dash_counts.dash_row_count, 0)
        or adoption.source_bev_dash_row_count
        is distinct from coalesce(fact_dash_counts.bev_dash_row_count, 0)
        or adoption.source_phev_dash_row_count
        is distinct from coalesce(fact_dash_counts.phev_dash_row_count, 0)

),

comparison_violations as (

    select
        current_row.month_end,
        current_row.vehicle_scope,
        'comparison_dash_mismatch' as violation_reason
    from adoption as current_row
    left join adoption as mom_row
        on
            current_row.vehicle_scope = mom_row.vehicle_scope
            and mom_row.month_end = last_day(
                date_sub(
                    date_trunc(current_row.month_end, month), interval 1 month
                )
            )
    left join adoption as yoy_row
        on
            current_row.vehicle_scope = yoy_row.vehicle_scope
            and yoy_row.month_end = last_day(
                date_sub(
                    date_trunc(current_row.month_end, month), interval 12 month
                )
            )
    left join fact_dash_counts as mom_counts
        on
            mom_row.month_end = mom_counts.month_end
            and mom_row.vehicle_scope = mom_counts.vehicle_scope
    left join fact_dash_counts as yoy_counts
        on
            yoy_row.month_end = yoy_counts.month_end
            and yoy_row.vehicle_scope = yoy_counts.vehicle_scope
    where
        current_row.mom_comparison_dash_row_count is distinct from (
            case
                when mom_row.month_end is not null
                    then coalesce(mom_counts.dash_row_count, 0)
            end
        )
        or current_row.mom_comparison_bev_dash_row_count is distinct from (
            case
                when mom_row.month_end is not null
                    then coalesce(mom_counts.bev_dash_row_count, 0)
            end
        )
        or current_row.mom_comparison_phev_dash_row_count is distinct from (
            case
                when mom_row.month_end is not null
                    then coalesce(mom_counts.phev_dash_row_count, 0)
            end
        )
        or current_row.yoy_comparison_dash_row_count is distinct from (
            case
                when yoy_row.month_end is not null
                    then coalesce(yoy_counts.dash_row_count, 0)
            end
        )
        or current_row.yoy_comparison_bev_dash_row_count is distinct from (
            case
                when yoy_row.month_end is not null
                    then coalesce(yoy_counts.bev_dash_row_count, 0)
            end
        )
        or current_row.yoy_comparison_phev_dash_row_count is distinct from (
            case
                when yoy_row.month_end is not null
                    then coalesce(yoy_counts.phev_dash_row_count, 0)
            end
        )

)

select
    month_end,
    vehicle_scope,
    violation_reason
from own_month_violations
union all
select
    month_end,
    vehicle_scope,
    violation_reason
from comparison_violations
