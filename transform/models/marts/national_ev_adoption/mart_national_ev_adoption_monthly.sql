{{ config(materialized='table') }}

{#
    National EV adoption at month_end x vehicle_scope: the five normalized vehicle
    types plus an all_vehicles rollup, exactly six rows per spine month. The spine
    is generated from first-of-month values and only then converted to month end,
    because stepping directly between month-end dates shifts the day of month
    across short months. Component stocks are independent conditional sums (not
    derived from each other), so the completeness gate can catch a contradictory
    classification instead of reconciling by construction. Incomplete rows keep
    their raw partial stocks and dash diagnostics but publish NULL shares;
    net-change/growth measures are NULL unless BOTH endpoint months are complete,
    because LAG would otherwise pull an incomplete month's partial stock into a
    plausible-looking indicator. Comparison dash counts are deliberately ungated:
    they exist to flag policy zeros inside the comparison base (e.g. a YoY rate
    computed against the dash-affected 2020-04 month).
#}

with adoption_facts as (

    select
        month_end,
        vehicle_type,
        vehicle_population,
        source_value_status,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version,
        source_release_key,
        source_retrieved_date,
        latest_source_month_end
    from {{ ref('fct_national_ev_adoption_monthly') }}

),

fact_bounds as (

    select
        date_trunc(min(month_end), month) as first_month_start,
        date_trunc(max(month_end), month) as latest_month_start
    from adoption_facts

),

month_spine as (

    select last_day(generated_month_start) as month_end
    from fact_bounds
    cross join unnest(
        generate_date_array(
            fact_bounds.first_month_start,
            fact_bounds.latest_month_start,
            interval 1 month
        )
    ) as generated_month_start

),

vehicle_scopes as (

    select
        scope.vehicle_scope,
        scope.expected_vehicle_category_count
    from unnest([
        struct('cars' as vehicle_scope, 1 as expected_vehicle_category_count),
        struct('taxis', 1),
        struct('motorcycles', 1),
        struct('goods_and_other_vehicles', 1),
        struct('buses', 1),
        struct('all_vehicles', 5)
    ]) as scope

),

scope_aggregates as (

    select
        month_spine.month_end,
        vehicle_scopes.vehicle_scope,
        vehicle_scopes.expected_vehicle_category_count,
        count(adoption_facts.vehicle_type) as fact_row_count,
        count(distinct adoption_facts.vehicle_type)
            as represented_vehicle_category_count,
        count(distinct adoption_facts.classification_version)
            as classification_version_count,
        sum(adoption_facts.vehicle_population) as total_vehicle_population,
        sum(
            case
                when adoption_facts.is_bev
                    then adoption_facts.vehicle_population
            end
        ) as bev_stock_raw,
        sum(
            case
                when adoption_facts.is_phev
                    then adoption_facts.vehicle_population
            end
        ) as phev_stock_raw,
        sum(
            case
                when adoption_facts.is_plug_in_vehicle
                    then adoption_facts.vehicle_population
            end
        ) as plug_in_stock_raw,
        sum(
            case
                when not adoption_facts.is_plug_in_vehicle
                    then adoption_facts.vehicle_population
            end
        ) as non_plug_in_stock_raw,
        sum(
            case
                when adoption_facts.powertrain_group = 'non_plug_in_hybrid'
                    then adoption_facts.vehicle_population
            end
        ) as non_plug_in_hybrid_stock_raw,
        countif(
            adoption_facts.source_value_status = 'source_dash_zero'
        ) as source_dash_row_count,
        countif(
            adoption_facts.source_value_status = 'source_dash_zero'
            and adoption_facts.is_bev
        ) as source_bev_dash_row_count,
        countif(
            adoption_facts.source_value_status = 'source_dash_zero'
            and adoption_facts.is_phev
        ) as source_phev_dash_row_count,
        max(adoption_facts.classification_version) as classification_version,
        max(adoption_facts.source_release_key) as source_release_key,
        max(adoption_facts.source_retrieved_date) as source_retrieved_date,
        max(adoption_facts.latest_source_month_end) as latest_source_month_end
    from month_spine
    cross join vehicle_scopes
    left join adoption_facts
        on
            month_spine.month_end = adoption_facts.month_end
            and (
                vehicle_scopes.vehicle_scope = 'all_vehicles'
                or vehicle_scopes.vehicle_scope = adoption_facts.vehicle_type
            )
    group by
        month_spine.month_end,
        vehicle_scopes.vehicle_scope,
        vehicle_scopes.expected_vehicle_category_count

),

scope_stocks as (

    select
        scope_aggregates.*,
        case
            when scope_aggregates.fact_row_count > 0
                then coalesce(scope_aggregates.bev_stock_raw, 0)
        end as bev_population,
        case
            when scope_aggregates.fact_row_count > 0
                then coalesce(scope_aggregates.phev_stock_raw, 0)
        end as phev_population,
        case
            when scope_aggregates.fact_row_count > 0
                then coalesce(scope_aggregates.plug_in_stock_raw, 0)
        end as plug_in_vehicle_population,
        case
            when scope_aggregates.fact_row_count > 0
                then coalesce(scope_aggregates.non_plug_in_stock_raw, 0)
        end as non_plug_in_vehicle_population,
        case
            when scope_aggregates.fact_row_count > 0
                then coalesce(scope_aggregates.non_plug_in_hybrid_stock_raw, 0)
        end as non_plug_in_hybrid_population
    from scope_aggregates

),

scope_status as (

    select
        scope_stocks.*,
        coalesce(
            scope_stocks.represented_vehicle_category_count
            = scope_stocks.expected_vehicle_category_count
            and scope_stocks.classification_version_count = 1
            and scope_stocks.bev_population + scope_stocks.phev_population
            = scope_stocks.plug_in_vehicle_population
            and scope_stocks.plug_in_vehicle_population
            + scope_stocks.non_plug_in_vehicle_population
            = scope_stocks.total_vehicle_population
            and scope_stocks.non_plug_in_hybrid_population
            <= scope_stocks.non_plug_in_vehicle_population,
            false
        ) as is_complete
    from scope_stocks

),

windowed as (

    select
        scope_status.*,
        lag(scope_status.is_complete, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_is_complete,
        lag(scope_status.bev_population, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_bev_population,
        lag(scope_status.phev_population, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_phev_population,
        lag(scope_status.plug_in_vehicle_population, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_plug_in_population,
        lag(scope_status.source_dash_row_count, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_comparison_dash_row_count,
        lag(scope_status.source_bev_dash_row_count, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_comparison_bev_dash_row_count,
        lag(scope_status.source_phev_dash_row_count, 1) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as mom_comparison_phev_dash_row_count,
        lag(scope_status.is_complete, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_is_complete,
        lag(scope_status.bev_population, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_bev_population,
        lag(scope_status.phev_population, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_phev_population,
        lag(scope_status.plug_in_vehicle_population, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_plug_in_population,
        lag(scope_status.source_dash_row_count, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_comparison_dash_row_count,
        lag(scope_status.source_bev_dash_row_count, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_comparison_bev_dash_row_count,
        lag(scope_status.source_phev_dash_row_count, 12) over (
            partition by scope_status.vehicle_scope
            order by scope_status.month_end
        ) as yoy_comparison_phev_dash_row_count
    from scope_status

),

measures as (

    select
        windowed.*,
        to_hex(md5(concat(
            cast(windowed.month_end as string),
            '|',
            windowed.vehicle_scope
        ))) as adoption_month_scope_key,
        case
            when windowed.is_complete then 'complete'
            else 'incomplete'
        end as adoption_data_status,
        case
            when windowed.is_complete
                then safe_divide(
                    windowed.bev_population,
                    windowed.total_vehicle_population
                )
        end as bev_share,
        case
            when windowed.is_complete
                then safe_divide(
                    windowed.phev_population,
                    windowed.total_vehicle_population
                )
        end as phev_share,
        case
            when windowed.is_complete
                then safe_divide(
                    windowed.plug_in_vehicle_population,
                    windowed.total_vehicle_population
                )
        end as plug_in_vehicle_share,
        case
            when windowed.is_complete and windowed.mom_is_complete
                then windowed.bev_population - windowed.mom_bev_population
        end as bev_net_change_mom,
        case
            when windowed.is_complete and windowed.mom_is_complete
                then safe_divide(
                    windowed.bev_population - windowed.mom_bev_population,
                    windowed.mom_bev_population
                )
        end as bev_growth_rate_mom,
        case
            when windowed.is_complete and windowed.yoy_is_complete
                then windowed.bev_population - windowed.yoy_bev_population
        end as bev_net_change_yoy,
        case
            when windowed.is_complete and windowed.yoy_is_complete
                then safe_divide(
                    windowed.bev_population - windowed.yoy_bev_population,
                    windowed.yoy_bev_population
                )
        end as bev_growth_rate_yoy,
        case
            when windowed.is_complete and windowed.mom_is_complete
                then windowed.phev_population - windowed.mom_phev_population
        end as phev_net_change_mom,
        case
            when windowed.is_complete and windowed.mom_is_complete
                then safe_divide(
                    windowed.phev_population - windowed.mom_phev_population,
                    windowed.mom_phev_population
                )
        end as phev_growth_rate_mom,
        case
            when windowed.is_complete and windowed.yoy_is_complete
                then windowed.phev_population - windowed.yoy_phev_population
        end as phev_net_change_yoy,
        case
            when windowed.is_complete and windowed.yoy_is_complete
                then safe_divide(
                    windowed.phev_population - windowed.yoy_phev_population,
                    windowed.yoy_phev_population
                )
        end as phev_growth_rate_yoy,
        case
            when windowed.is_complete and windowed.mom_is_complete
                then
                    windowed.plug_in_vehicle_population
                    - windowed.mom_plug_in_population
        end as plug_in_vehicle_net_change_mom,
        case
            when windowed.is_complete and windowed.mom_is_complete
                then safe_divide(
                    windowed.plug_in_vehicle_population
                    - windowed.mom_plug_in_population,
                    windowed.mom_plug_in_population
                )
        end as plug_in_vehicle_growth_rate_mom,
        case
            when windowed.is_complete and windowed.yoy_is_complete
                then
                    windowed.plug_in_vehicle_population
                    - windowed.yoy_plug_in_population
        end as plug_in_vehicle_net_change_yoy,
        case
            when windowed.is_complete and windowed.yoy_is_complete
                then safe_divide(
                    windowed.plug_in_vehicle_population
                    - windowed.yoy_plug_in_population,
                    windowed.yoy_plug_in_population
                )
        end as plug_in_vehicle_growth_rate_yoy
    from windowed

),

final as (

    select
        measures.adoption_month_scope_key,
        measures.month_end,
        measures.vehicle_scope,
        measures.adoption_data_status,
        measures.represented_vehicle_category_count,
        measures.expected_vehicle_category_count,
        measures.total_vehicle_population,
        measures.bev_population,
        measures.phev_population,
        measures.plug_in_vehicle_population,
        measures.non_plug_in_vehicle_population,
        measures.non_plug_in_hybrid_population,
        measures.bev_share,
        measures.phev_share,
        measures.plug_in_vehicle_share,
        measures.bev_net_change_mom,
        measures.bev_growth_rate_mom,
        measures.bev_net_change_yoy,
        measures.bev_growth_rate_yoy,
        measures.phev_net_change_mom,
        measures.phev_growth_rate_mom,
        measures.phev_net_change_yoy,
        measures.phev_growth_rate_yoy,
        measures.plug_in_vehicle_net_change_mom,
        measures.plug_in_vehicle_growth_rate_mom,
        measures.plug_in_vehicle_net_change_yoy,
        measures.plug_in_vehicle_growth_rate_yoy,
        measures.source_dash_row_count,
        measures.source_bev_dash_row_count,
        measures.source_phev_dash_row_count,
        measures.mom_comparison_dash_row_count,
        measures.mom_comparison_bev_dash_row_count,
        measures.mom_comparison_phev_dash_row_count,
        measures.yoy_comparison_dash_row_count,
        measures.yoy_comparison_bev_dash_row_count,
        measures.yoy_comparison_phev_dash_row_count,
        measures.classification_version,
        measures.source_release_key,
        measures.source_retrieved_date,
        measures.latest_source_month_end
    from measures

)

select * from final
