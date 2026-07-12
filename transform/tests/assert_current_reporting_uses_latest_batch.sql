-- A current model's sole batch must match the latest snapshot in its parent fact.
with expected_ev as (
    select batch_id
    from {{ ref('fct_ev_location_availability') }}
    group by batch_id
    order by max(snapshot_time) desc, batch_id desc
    limit 1
),

expected_carpark as (
    select batch_id
    from {{ ref('fct_carpark_availability') }}
    group by batch_id
    order by max(snapshot_time) desc, batch_id desc
    limit 1
),

expected_traffic as (
    select batch_id
    from {{ ref('fct_traffic_congestion') }}
    group by batch_id
    order by max(snapshot_time) desc, batch_id desc
    limit 1
)

select 'rpt_ev_availability_current' as model_name, c.batch_id
from {{ ref('rpt_ev_availability_current') }} as c
cross join expected_ev as expected
where c.batch_id != expected.batch_id

union all

select 'rpt_carpark_availability_current' as model_name, c.batch_id
from {{ ref('rpt_carpark_availability_current') }} as c
cross join expected_carpark as expected
where c.batch_id != expected.batch_id

union all

select 'rpt_traffic_congestion_current' as model_name, c.batch_id
from {{ ref('rpt_traffic_congestion_current') }} as c
cross join expected_traffic as expected
where c.batch_id != expected.batch_id
