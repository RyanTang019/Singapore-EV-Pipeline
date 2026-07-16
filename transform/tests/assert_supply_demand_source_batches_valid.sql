-- The daily fact relies on one non-null source time and SGT date per batch.
-- Derived unknown connector counts must never be negative.
with batch_profiles as (

    select
        batch_id,
        any_value(snapshot_time) as snapshot_time,
        any_value(snapshot_date) as snapshot_date,
        count(distinct snapshot_time) as source_snapshot_time_count,
        countif(snapshot_time is null) as null_snapshot_time_row_count,
        count(distinct ingested_at) as ingested_at_count,
        countif(ingested_at is null) as null_ingested_at_row_count,
        count(distinct snapshot_date) as snapshot_date_count,
        countif(snapshot_date is null) as null_snapshot_date_row_count,
        sum(
            total_connectors
            - available_connectors
            - occupied_connectors
            - unavailable_connectors
        ) as network_unknown_connector_count
    from {{ ref('fct_ev_location_availability') }}
    group by batch_id

)

select *
from batch_profiles
where
    source_snapshot_time_count != 1
    or null_snapshot_time_row_count > 0
    or ingested_at_count != 1
    or null_ingested_at_row_count > 0
    or snapshot_date_count != 1
    or null_snapshot_date_row_count > 0
    or snapshot_date != date(snapshot_time, 'Asia/Singapore')
    or network_unknown_connector_count < 0
