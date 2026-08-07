-- Zero rows deliberately fail: the current reporting boundary publishes only a
-- full six-scope complete slice for a single reporting month. Column tests pass
-- vacuously on an empty table, so the row-count requirement lives here.
select
    count(*) as row_count,
    count(distinct vehicle_scope) as scope_count,
    count(distinct as_of_month) as as_of_month_count,
    countif(adoption_data_status = 'complete') as complete_count
from {{ ref('rpt_national_ev_adoption_current') }}
having
    count(*) != 6
    or count(distinct vehicle_scope) != 6
    or count(distinct as_of_month) != 1
    or countif(adoption_data_status = 'complete') != 6
