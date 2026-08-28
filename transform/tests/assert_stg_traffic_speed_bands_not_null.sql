-- Passes (0 rows) when every JSON-derived column is populated.
--
-- Replaces four per-column not_null tests. stg_traffic_speed_bands is a view
-- over raw JSON, so every column is computed from payload and BigQuery has
-- nothing to prune -- a single-column not_null test still re-parses the whole
-- payload (~1.1 GiB). Four such tests cost four full scans; this costs one.
--
-- MUST stay a single pass. Writing it as a UNION ALL of per-column selects
-- reintroduces one scan per column and saves nothing.
--
-- On failure the returned row names every column that has nulls, and the
-- aggregate bounds the output to one row -- a total feed failure across all
-- 9.46M rows cannot dump a large result set. To see the offending rows,
-- query the model directly with the column that reported a non-zero count.
--
-- batch_id/ingested_at are deliberately absent: mode=REQUIRED in raw, so
-- BigQuery already enforces them (see stg_models.yml).
with checks as (
    select
        countif(link_id is null) as link_id_nulls,
        countif(snapshot_time is null) as snapshot_time_nulls,
        countif(speed_band is null) as speed_band_nulls,
        countif(is_no_reading is null) as is_no_reading_nulls
    from {{ ref('stg_traffic_speed_bands') }}
)

select
    link_id_nulls,
    snapshot_time_nulls,
    speed_band_nulls,
    is_no_reading_nulls
from checks
where
    link_id_nulls > 0
    or snapshot_time_nulls > 0
    or speed_band_nulls > 0
    or is_no_reading_nulls > 0
