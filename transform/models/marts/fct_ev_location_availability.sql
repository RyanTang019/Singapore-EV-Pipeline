-- One row per location (postal_code) per snapshot (batch_id): connector counts + availability
-- rate over time. Aggregates the connector-grain staging model up to location grain — the
-- table a "utilisation over time / map" dashboard reads. Keyed on batch_id (the unique
-- ingestion event), with snapshot_time exposed as the chart time axis.

{{ config(materialized='table') }}

select
    to_hex(md5(concat(batch_id, '|', postal_code))) as location_availability_key,

    -- grain keys
    batch_id,
    postal_code,

    -- time axis / attributes (constant within a batch+postal, so any_value is safe)
    any_value(snapshot_time)  as snapshot_time,
    any_value(ingested_at)    as ingested_at,
    any_value(location_name)  as location_name,
    any_value(address)        as address,
    any_value(latitude)       as latitude,
    any_value(longitude)      as longitude,

    -- measures
    count(*)                                          as total_connectors,
    countif(connector_status = 'available')           as available_connectors,
    countif(connector_status = 'occupied')            as occupied_connectors,
    countif(connector_status = 'unavailable')         as unavailable_connectors,
    -- 'unknown' connectors count toward total but no named bucket, so the three buckets
    -- may sum to <= total. safe_divide returns NULL only if total = 0 (impossible here).
    safe_divide(
        countif(connector_status = 'available'),
        count(*)
    ) as availability_rate

from {{ ref('stg_ev_charger_availability') }}
group by batch_id, postal_code
