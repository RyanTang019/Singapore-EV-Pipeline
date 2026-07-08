{# One row per road link (LinkID) per snapshot (batch_id). Explodes the opaque
   v3/TrafficSpeedBands payload (records under $.value) into typed columns.
   LTA quirks handled: the numeric fields all arrive as JSON strings (cast
   here); SpeedBand is documented 1-8 but an undocumented 0 (no speed reading)
   also appears and is passed through untouched so it stays visible. There is no
   timestamp inside the payload (unlike EVCBatch), so ingested_at is the only
   snapshot time. Downstream models read this, never the raw JSON. #}

{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'traffic_speed_bands') }}
),

exploded as (
    select
        s.batch_id,
        s.ingested_at,

        -- speed measures (JSON strings -> int)
        cast(json_value(link, '$.SpeedBand') as int64) as speed_band,
        cast(json_value(link, '$.MinimumSpeed') as int64) as minimum_speed,
        cast(json_value(link, '$.MaximumSpeed') as int64) as maximum_speed,

        -- link geometry endpoints (JSON strings -> float)
        cast(json_value(link, '$.StartLat') as float64) as start_latitude,
        cast(json_value(link, '$.StartLon') as float64) as start_longitude,
        cast(json_value(link, '$.EndLat') as float64) as end_latitude,
        cast(json_value(link, '$.EndLon') as float64) as end_longitude,

        -- link identity/attributes (the grain is link_id); ordered after the
        -- casts to satisfy sqlfluff ST06 (casts before bare extractions)
        json_value(link, '$.LinkID') as link_id,
        json_value(link, '$.RoadName') as road_name,
        json_value(link, '$.RoadCategory') as road_category

    from source as s,
        unnest(json_query_array(s.payload, '$.value')) as link
),

final as (
    select * from exploded
)

select * from final
