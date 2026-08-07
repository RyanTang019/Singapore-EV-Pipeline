{{ config(materialized='table', contract={'enforced': true}) }}

{#
    Fail-closed current national EV adoption slice: exactly the latest mart month, and only
    when that month is a full six-scope complete slice. The candidate is the raw max(month_end)
    over the whole mart, never the latest complete month, so a stale incomplete latest month
    fails the build here instead of silently shifting the report back to an older month. When
    the candidate does not validate the model emits zero rows; the singular tests then turn that
    empty output into a build failure rather than a blank published dashboard. Every date is
    projected as a string so a historical Looker date control cannot suppress the current-slice
    scorecards.
#}

with latest_candidate as (

    select max(month_end) as month_end
    from {{ ref('mart_national_ev_adoption_monthly') }}

),

validated_candidate as (

    select latest_candidate.month_end
    from {{ ref('mart_national_ev_adoption_monthly') }} as mart
    inner join latest_candidate
        on mart.month_end = latest_candidate.month_end
    group by latest_candidate.month_end
    having
        count(*) = 6
        and countif(mart.adoption_data_status = 'complete') = 6
        and count(distinct mart.classification_version) = 1
        and countif(
            mart.bev_population + mart.phev_population
            = mart.plug_in_vehicle_population
            and mart.plug_in_vehicle_population
            + mart.non_plug_in_vehicle_population
            = mart.total_vehicle_population
        ) = 6

),

reporting_projection as (

    select
        mart.*,
        format_date('%Y-%m', mart.month_end) as as_of_month,
        concat(
            'Retrieved ',
            format_date('%Y-%m-%d', mart.source_retrieved_date)
        ) as source_retrieved,
        format_date('%Y-%m', mart.latest_source_month_end)
            as latest_source_month
    from {{ ref('mart_national_ev_adoption_monthly') }} as mart
    inner join validated_candidate
        on mart.month_end = validated_candidate.month_end

)

select
    reporting_projection.adoption_month_scope_key,
    reporting_projection.as_of_month,
    reporting_projection.vehicle_scope,
    reporting_projection.adoption_data_status,
    reporting_projection.represented_vehicle_category_count,
    reporting_projection.expected_vehicle_category_count,
    reporting_projection.total_vehicle_population,
    reporting_projection.bev_population,
    reporting_projection.phev_population,
    reporting_projection.plug_in_vehicle_population,
    reporting_projection.non_plug_in_vehicle_population,
    reporting_projection.non_plug_in_hybrid_population,
    reporting_projection.bev_share,
    reporting_projection.phev_share,
    reporting_projection.plug_in_vehicle_share,
    reporting_projection.bev_net_change_mom,
    reporting_projection.bev_growth_rate_mom,
    reporting_projection.bev_net_change_yoy,
    reporting_projection.bev_growth_rate_yoy,
    reporting_projection.phev_net_change_mom,
    reporting_projection.phev_growth_rate_mom,
    reporting_projection.phev_net_change_yoy,
    reporting_projection.phev_growth_rate_yoy,
    reporting_projection.plug_in_vehicle_net_change_mom,
    reporting_projection.plug_in_vehicle_growth_rate_mom,
    reporting_projection.plug_in_vehicle_net_change_yoy,
    reporting_projection.plug_in_vehicle_growth_rate_yoy,
    reporting_projection.source_dash_row_count,
    reporting_projection.source_bev_dash_row_count,
    reporting_projection.source_phev_dash_row_count,
    reporting_projection.mom_comparison_dash_row_count,
    reporting_projection.mom_comparison_bev_dash_row_count,
    reporting_projection.mom_comparison_phev_dash_row_count,
    reporting_projection.yoy_comparison_dash_row_count,
    reporting_projection.yoy_comparison_bev_dash_row_count,
    reporting_projection.yoy_comparison_phev_dash_row_count,
    reporting_projection.classification_version,
    reporting_projection.source_release_key,
    reporting_projection.source_retrieved,
    reporting_projection.latest_source_month
from reporting_projection
