{# One row per carpark per lot type (CarParkID + LotType) per snapshot
   (batch_id). CarParkID alone is NOT unique -- a carpark reports lots per
   vehicle class, so ~2.6k rows span ~2.1k carparks. Explodes the opaque
   CarParkAvailabilityv2 payload (records under $.value).
   LTA quirks handled: Location is a single "lat lon" string (split here, and
   ~1 row/batch has it null -> safe_cast leaves lat/long null); LotType is
   documented C/H/Y (Cars / Heavy / motorcYcles) but an undocumented "S" also
   appears and is passed through untouched; Area is empty for ~98% of rows
   (Development is the usable site name). The feed carries AvailableLots ONLY --
   there is no total capacity, so occupancy cannot be derived from this source
   alone. The payload has NO internal timestamp (top level is just {value[]}),
   so snapshot_time is set to ingested_at (already a true UTC instant) -- this
   keeps a uniform snapshot_time interface across all staging models.
   NOT-UNIQUE GRAIN: the feed occasionally repeats the same carpark_id + lot_type
   within a single snapshot (~81 rows across history so far, nearly all exact
   duplicates), so (batch_id, carpark_id, lot_type) is not a strict unique key --
   downstream models must dedupe/aggregate rather than assume one row per key.
   Downstream models read this, never the raw JSON. #}

{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'carpark_availability') }}
),

exploded as (
    select
        s.batch_id,
        s.ingested_at,

        -- no timestamp in this payload; ingested_at (true UTC) is the snapshot
        -- time. Aliased for a uniform snapshot_time interface across staging.
        s.ingested_at as snapshot_time,

        -- array position in the payload; the last-observed dedupe key for
        -- repeated (carpark_id, lot_type) rows downstream. Bare column, so it
        -- sits with the simple targets (ST06: simple targets before casts).
        source_offset,

        -- measure (available lots only; no total capacity in this feed)
        cast(json_value(lot, '$.AvailableLots') as int64) as available_lots,

        -- Location is a single "lat lon" string; split + cast, tolerating the
        -- ~1 null/batch via safe_cast/safe_offset
        safe_cast(
            split(json_value(lot, '$.Location'), ' ')[safe_offset(0)] as float64
        ) as latitude,
        safe_cast(
            split(json_value(lot, '$.Location'), ' ')[safe_offset(1)] as float64
        ) as longitude,

        -- identity + attributes (grain: carpark_id x lot_type); ordered after
        -- the casts to satisfy sqlfluff ST06 (casts before bare extractions)
        json_value(lot, '$.CarParkID') as carpark_id,
        json_value(lot, '$.LotType') as lot_type,
        json_value(lot, '$.Development') as development,
        json_value(lot, '$.Area') as area,
        json_value(lot, '$.Agency') as agency

    from source as s,
        unnest(json_query_array(s.payload, '$.value')) as lot
        with offset as source_offset
),

final as (
    select * from exploded
)

select * from final
