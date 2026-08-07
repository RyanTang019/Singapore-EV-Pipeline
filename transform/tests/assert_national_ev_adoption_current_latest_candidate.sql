-- The report must reflect the mart's raw latest month, never a stale older
-- complete month. The candidate is max(month_end) over the whole mart (not just
-- complete months), so a stale incomplete latest month fails here instead of
-- silently shifting the candidate.
with latest_candidate as (

    select max(month_end) as month_end
    from {{ ref('mart_national_ev_adoption_monthly') }}

),

report_summary as (

    select
        count(*) as row_count,
        count(distinct as_of_month) as as_of_month_count,
        any_value(as_of_month) as as_of_month
    from {{ ref('rpt_national_ev_adoption_current') }}

)

select
    report_summary.*,
    latest_candidate.month_end
from latest_candidate
cross join report_summary
where
    report_summary.row_count != 6
    or report_summary.as_of_month_count != 1
    or report_summary.as_of_month
    != format_date('%Y-%m', latest_candidate.month_end)
