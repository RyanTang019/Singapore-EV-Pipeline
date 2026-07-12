-- Each current reporting model must contain exactly one ingestion batch.
select 'rpt_ev_availability_current' as model_name,
       count(distinct batch_id) as batch_count
from {{ ref('rpt_ev_availability_current') }}
having count(distinct batch_id) != 1

union all

select 'rpt_carpark_availability_current' as model_name,
       count(distinct batch_id) as batch_count
from {{ ref('rpt_carpark_availability_current') }}
having count(distinct batch_id) != 1

union all

select 'rpt_traffic_congestion_current' as model_name,
       count(distinct batch_id) as batch_count
from {{ ref('rpt_traffic_congestion_current') }}
having count(distinct batch_id) != 1
