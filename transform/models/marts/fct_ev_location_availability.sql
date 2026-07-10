-- One row per location (postal_code) per snapshot (batch_id): connector counts
-- + availability rate over time. Aggregates the connector-grain staging model
-- up to location grain — the table a "utilisation over time / map" dashboard
-- reads. Keyed on batch_id (the unique ingestion event), with snapshot_time
-- exposed as the chart time axis.

{{ config(materialized='table') }}

select
    batch_id,

    -- grain keys
    postal_code,
    to_hex(md5(concat(batch_id, '|', postal_code)))
        as location_availability_key,

    -- time axis / attributes (constant within a batch+postal, so any_value
    -- is safe)
    any_value(snapshot_time) as snapshot_time,
    any_value(ingested_at) as ingested_at,
    any_value(location_name) as location_name,
    any_value(address) as address,
    any_value(latitude) as latitude,
    any_value(longitude) as longitude,

    -- spatial + time attributes (planning_area constant within a postal code,
    -- time features constant within a batch -> any_value is safe)
    any_value(planning_area) as planning_area,
    any_value(snapshot_date) as snapshot_date,
    any_value(hour_of_day) as hour_of_day,
    any_value(day_of_week) as day_of_week,

    -- measures
    count(*) as total_connectors,
    countif(connector_status = 'available') as available_connectors,
    countif(connector_status = 'occupied') as occupied_connectors,
    countif(connector_status = 'unavailable') as unavailable_connectors,
    -- 'unknown' connectors count toward total but no named bucket, so the
    -- three buckets may sum to <= total. safe_divide returns NULL only if
    -- total = 0 (impossible here).
    safe_divide(
        countif(connector_status = 'available'),
        count(*)
    ) as availability_rate

from {{ ref('int_ev_tagged') }}
group by batch_id, postal_code
