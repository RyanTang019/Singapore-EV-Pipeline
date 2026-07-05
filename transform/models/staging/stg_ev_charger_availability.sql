-- One row per EV connector per snapshot (the finest grain: location -> charging point ->
-- plug type -> connector). Explodes the opaque EVCBatch payload and interprets the
-- documented LTA quirks (misspelled longtitude, the two status vocabularies, the
-- undocumented "100" point status). Downstream models read this, never the raw JSON.

{{ config(materialized='view') }}

with snapshots as (
    select
        batch_id,
        ingested_at,
        payload
    from {{ source('raw', 'ev_charger_availability') }}
),

connectors as (
    select
        s.batch_id,
        s.ingested_at,
        -- true snapshot time from inside the payload, distinct from ingested_at (our fetch time)
        cast(json_value(s.payload, '$.LastUpdatedTime') as timestamp) as snapshot_time,

        -- location level
        json_value(loc, '$.name')                       as location_name,
        json_value(loc, '$.address')                    as address,
        json_value(loc, '$.postalCode')                 as postal_code,
        cast(json_value(loc, '$.latitude')   as float64) as latitude,
        cast(json_value(loc, '$.longtitude') as float64) as longitude,  -- API misspells "longitude"

        -- charging-point level
        json_value(pt, '$.name')                        as point_name,
        json_value(pt, '$.operator')                    as operator,
        json_value(pt, '$.operatingHours')              as operating_hours,
        json_value(pt, '$.status')                      as point_status_raw,

        -- plug-type level
        json_value(plug, '$.plugType')                  as plug_type,
        json_value(plug, '$.current')                   as current_type,
        json_value(plug, '$.powerRating')               as power_rating,
        json_value(plug, '$.price')                     as price,
        json_value(plug, '$.priceType')                 as price_type,

        -- connector level (the grain)
        json_value(conn, '$.evCpId')                    as connector_id,
        json_value(conn, '$.status')                    as connector_status_raw

    from snapshots s,
        unnest(json_query_array(s.payload, '$.evLocationsData')) as loc,
        unnest(json_query_array(loc,       '$.chargingPoints'))  as pt,
        unnest(json_query_array(pt,        '$.plugTypes'))       as plug,
        unnest(json_query_array(plug,      '$.evIds'))           as conn
)

select
    *,
    -- connector status: "1"=available, "0"=occupied, ""=unavailable (per LTA, verified)
    case connector_status_raw
        when '1' then 'available'
        when '0' then 'occupied'
        when ''  then 'unavailable'
        else 'unknown'                       -- surfaces any NEW undocumented value loudly
    end as connector_status,

    -- point status: same vocab PLUS an undocumented "100" (~1.5%, likely maintenance/offline).
    -- Keep it as its own bucket rather than folding into 'unknown' so it stays visible.
    case point_status_raw
        when '1'   then 'available'
        when '0'   then 'occupied'
        when ''    then 'unavailable'
        when '100' then 'offline_100'
        else 'unknown'
    end as point_status

from connectors
