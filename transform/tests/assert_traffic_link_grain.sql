-- Passes (0 rows) when each snapshot reports each link at most once.
-- fct_traffic_congestion counts rows, so a duplicated (batch_id, link_id) would
-- inflate link_count and skew congested_link_rate. If this ever fails, add a
-- per-link dedupe CTE in fct_traffic_congestion
-- (row_number() over (partition by batch_id, link_id order by ...) = 1)
-- BEFORE the area aggregation.
select
    batch_id,
    link_id,
    count(*) as n
from {{ ref('stg_traffic_speed_bands') }}
group by batch_id, link_id
having count(*) > 1
