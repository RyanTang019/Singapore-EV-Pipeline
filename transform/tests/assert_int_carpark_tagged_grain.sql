-- Passes (0 rows) when the dedupe leaves exactly one row per grain key.
select batch_id, carpark_id, lot_type, count(*) as n
from {{ ref('int_carpark_tagged') }}
group by batch_id, carpark_id, lot_type
having count(*) > 1
