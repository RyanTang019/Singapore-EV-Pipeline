-- The observed source history began on 2026-06-08, after the controlled
-- 2025-06-30 population reference date. An earlier backfill must first add a
-- compatible release rather than silently publishing NULL population rows.
select
    snapshot_date,
    planning_area,
    population_release_key,
    source_reference_date
from {{ ref('fct_supply_demand_daily') }}
where
    population_release_key is null
    or population_year is null
    or source_reference_date is null
    or source_published_date is null
    or source_retrieved_date is null
    or planning_geography_version is null
    or population_data_status is null
