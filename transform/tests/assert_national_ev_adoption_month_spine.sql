{#
    The fact must cover a continuous month spine from its first to its latest month, carry all
    five normalized vehicle types every month, and reconcile row-for-row with the staged
    observations it is built from. The spine is generated from first-of-month values and only
    then converted to month end, because stepping directly between month-end dates shifts the
    day of month across short months. Empty result = pass.
#}

with fact_bounds as (

    select
        date_trunc(min(month_end), month) as first_month_start,
        date_trunc(max(month_end), month) as latest_month_start
    from {{ ref('fct_national_ev_adoption_monthly') }}

),

expected_months as (

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

fact_months as (

    select
        month_end,
        count(*) as fact_row_count,
        count(distinct vehicle_type) as vehicle_type_count
    from {{ ref('fct_national_ev_adoption_monthly') }}
    group by month_end

),

staged_months as (

    select
        month_end,
        count(*) as staged_row_count
    from {{ ref('stg_lta_monthly_vehicle_population_by_fuel') }}
    group by month_end

),

spine_coverage as (

    select
        expected_months.month_end as expected_month_end,
        fact_months.fact_row_count,
        fact_months.vehicle_type_count,
        fact_months.month_end as fact_month_end,
        coalesce(expected_months.month_end, fact_months.month_end)
            as month_end
    from expected_months
    full outer join fact_months
        on expected_months.month_end = fact_months.month_end

)

select
    spine_coverage.expected_month_end,
    spine_coverage.fact_month_end,
    spine_coverage.fact_row_count,
    spine_coverage.vehicle_type_count,
    staged_months.staged_row_count,
    coalesce(spine_coverage.month_end, staged_months.month_end) as month_end
from spine_coverage
full outer join staged_months
    on spine_coverage.month_end = staged_months.month_end
where
    spine_coverage.expected_month_end is null
    or spine_coverage.fact_month_end is null
    or staged_months.month_end is null
    or spine_coverage.vehicle_type_count != 5
    or spine_coverage.fact_row_count != staged_months.staged_row_count
