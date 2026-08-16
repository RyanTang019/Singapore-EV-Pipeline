{#
    Every MoM/YoY net-change and growth measure must match a direct self-join
    recomputation whose comparison month is derived with the month-safe
    LAST_DAY(DATE_SUB(DATE_TRUNC(...))) expression, not LAG assumptions. The
    expected value is NULL unless both the current row and its comparison row
    are complete, so any published measure with an incomplete endpoint is
    flagged exactly like a wrong number. IS DISTINCT FROM treats a NULL/value
    disagreement as a violation. Empty result = pass.
#}

with adoption as (

    select * from {{ ref('mart_national_ev_adoption_monthly') }}

),

recomputed as (

    select
        current_row.month_end,
        current_row.vehicle_scope,
        current_row.bev_net_change_mom,
        current_row.bev_growth_rate_mom,
        current_row.bev_net_change_yoy,
        current_row.bev_growth_rate_yoy,
        current_row.phev_net_change_mom,
        current_row.phev_growth_rate_mom,
        current_row.phev_net_change_yoy,
        current_row.phev_growth_rate_yoy,
        current_row.plug_in_vehicle_net_change_mom,
        current_row.plug_in_vehicle_growth_rate_mom,
        current_row.plug_in_vehicle_net_change_yoy,
        current_row.plug_in_vehicle_growth_rate_yoy,
        mom_row.bev_population as mom_bev_population,
        yoy_row.bev_population as yoy_bev_population,
        mom_row.phev_population as mom_phev_population,
        yoy_row.phev_population as yoy_phev_population,
        mom_row.plug_in_vehicle_population as mom_plug_in_population,
        yoy_row.plug_in_vehicle_population as yoy_plug_in_population,
        current_row.adoption_data_status = 'complete'
        and mom_row.adoption_data_status = 'complete' as mom_pair_complete,
        current_row.adoption_data_status = 'complete'
        and yoy_row.adoption_data_status = 'complete' as yoy_pair_complete,
        current_row.bev_population - mom_row.bev_population as mom_bev_diff,
        current_row.bev_population - yoy_row.bev_population as yoy_bev_diff,
        current_row.phev_population - mom_row.phev_population as mom_phev_diff,
        current_row.phev_population - yoy_row.phev_population as yoy_phev_diff,
        current_row.plug_in_vehicle_population
        - mom_row.plug_in_vehicle_population as mom_plug_in_diff,
        current_row.plug_in_vehicle_population
        - yoy_row.plug_in_vehicle_population as yoy_plug_in_diff
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

),

expected as (

    select
        recomputed.*,
        case when mom_pair_complete then mom_bev_diff end
            as expected_bev_net_change_mom,
        case
            when mom_pair_complete
                then safe_divide(mom_bev_diff, mom_bev_population)
        end as expected_bev_growth_rate_mom,
        case when yoy_pair_complete then yoy_bev_diff end
            as expected_bev_net_change_yoy,
        case
            when yoy_pair_complete
                then safe_divide(yoy_bev_diff, yoy_bev_population)
        end as expected_bev_growth_rate_yoy,
        case when mom_pair_complete then mom_phev_diff end
            as expected_phev_net_change_mom,
        case
            when mom_pair_complete
                then safe_divide(mom_phev_diff, mom_phev_population)
        end as expected_phev_growth_rate_mom,
        case when yoy_pair_complete then yoy_phev_diff end
            as expected_phev_net_change_yoy,
        case
            when yoy_pair_complete
                then safe_divide(yoy_phev_diff, yoy_phev_population)
        end as expected_phev_growth_rate_yoy,
        case when mom_pair_complete then mom_plug_in_diff end
            as expected_plug_in_net_change_mom,
        case
            when mom_pair_complete
                then safe_divide(mom_plug_in_diff, mom_plug_in_population)
        end as expected_plug_in_growth_rate_mom,
        case when yoy_pair_complete then yoy_plug_in_diff end
            as expected_plug_in_net_change_yoy,
        case
            when yoy_pair_complete
                then safe_divide(yoy_plug_in_diff, yoy_plug_in_population)
        end as expected_plug_in_growth_rate_yoy
    from recomputed

)

select
    month_end,
    vehicle_scope
from expected
where
    bev_net_change_mom is distinct from expected_bev_net_change_mom
    or bev_growth_rate_mom is distinct from expected_bev_growth_rate_mom
    or bev_net_change_yoy is distinct from expected_bev_net_change_yoy
    or bev_growth_rate_yoy is distinct from expected_bev_growth_rate_yoy
    or phev_net_change_mom is distinct from expected_phev_net_change_mom
    or phev_growth_rate_mom is distinct from expected_phev_growth_rate_mom
    or phev_net_change_yoy is distinct from expected_phev_net_change_yoy
    or phev_growth_rate_yoy is distinct from expected_phev_growth_rate_yoy
    or plug_in_vehicle_net_change_mom
    is distinct from expected_plug_in_net_change_mom
    or plug_in_vehicle_growth_rate_mom
    is distinct from expected_plug_in_growth_rate_mom
    or plug_in_vehicle_net_change_yoy
    is distinct from expected_plug_in_net_change_yoy
    or plug_in_vehicle_growth_rate_yoy
    is distinct from expected_plug_in_growth_rate_yoy
