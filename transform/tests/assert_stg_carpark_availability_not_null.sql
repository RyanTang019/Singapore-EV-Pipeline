-- Passes (0 rows) when every JSON-derived column is populated.
--
-- Replaces three per-column not_null tests. stg_carpark_availability is a view
-- over raw JSON, so a single-column not_null test re-parses the whole payload
-- (~43.8 MiB); three such tests cost three full scans, this costs one.
--
-- MUST stay a single pass -- see assert_stg_traffic_speed_bands_not_null.sql.
--
-- Only three columns are checked because four of this model's original seven
-- not_null tests were structurally incapable of failing: batch_id/ingested_at
-- are mode=REQUIRED in raw, snapshot_time is a bare alias of ingested_at (NOT
-- payload-parsed, unlike the EV and traffic columns of the same name), and
-- source_offset comes from UNNEST ... WITH OFFSET. See stg_models.yml.
--
-- latitude/longitude are excluded on purpose: the feed carries ~1 null
-- Location per batch and the model uses safe_cast/safe_offset to tolerate it,
-- so nulls there are expected, not a defect.
with checks as (
    select
        countif(carpark_id is null) as carpark_id_nulls,
        countif(lot_type is null) as lot_type_nulls,
        countif(available_lots is null) as available_lots_nulls
    from {{ ref('stg_carpark_availability') }}
)

select
    carpark_id_nulls,
    lot_type_nulls,
    available_lots_nulls
from checks
where
    carpark_id_nulls > 0
    or lot_type_nulls > 0
    or available_lots_nulls > 0
