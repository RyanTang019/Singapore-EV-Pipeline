-- Passes (0 rows) when every JSON-derived column is populated.
--
-- Replaces two per-column not_null tests. stg_ev_charger_availability is a
-- view over raw JSON, so a single-column not_null test re-parses the whole
-- payload (~298 MiB); two such tests cost two full scans, this costs one.
--
-- MUST stay a single pass -- see assert_stg_traffic_speed_bands_not_null.sql.
--
-- The connector_status and point_status accepted_values tests are DELIBERATELY
-- left standalone in stg_models.yml rather than folded in here. They are the
-- only tests in staging that catch LTA vocabulary drift (the undocumented
-- '100' -> offline_100 already in the decode is exactly that), and an
-- accepted_values failure needs the offending VALUE to be actionable, not just
-- a count. Keeping them separate costs ~597 MiB per build; that is the price
-- of a usable failure message on the checks most likely to actually fire.
--
-- batch_id is deliberately absent: mode=REQUIRED in raw (see stg_models.yml).
with checks as (
    select
        countif(connector_id is null) as connector_id_nulls,
        countif(snapshot_time is null) as snapshot_time_nulls
    from {{ ref('stg_ev_charger_availability') }}
)

select
    connector_id_nulls,
    snapshot_time_nulls
from checks
where
    connector_id_nulls > 0
    or snapshot_time_nulls > 0
