-- Fails if link_count + no_reading_link_count does not equal the total tagged
-- observations feeding each (batch_id, planning_area) row.
with expected as (
    select
        s.batch_id,
        l.planning_area,
        count(*) as total_links
    from {{ ref('stg_traffic_speed_bands') }} as s
    inner join {{ ref('int_traffic_links') }} as l
        on s.link_id = l.link_id
    where l.planning_area is not null
    group by s.batch_id, l.planning_area
)

select f.traffic_congestion_key
from {{ ref('fct_traffic_congestion') }} as f
inner join expected as e
    on f.batch_id = e.batch_id and f.planning_area = e.planning_area
where f.link_count + f.no_reading_link_count != e.total_links
