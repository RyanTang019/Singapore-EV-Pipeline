-- Fails (returns a row) unless there are exactly 55 planning areas.
select count(*) as n from {{ ref('dim_planning_area') }} having count(*) != 55
