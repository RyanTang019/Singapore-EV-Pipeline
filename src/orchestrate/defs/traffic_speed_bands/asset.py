"""Dagster asset: TrafficSpeedBands snapshot -> ONE opaque raw row -> BigQuery (WRITE_APPEND).

Deliberately near-identical to ev_charger_availability/asset.py: same 4-column RAW_SCHEMA,
same CREATE_IF_NEEDED load, same batch_id/ingested_at stamping. Only source_name, the
fetch call, and the metadata count differ. The duplication is intentional (rule of three)
and must NOT be abstracted yet — it is the evidence for the config-driven factory (concern
#1). `GCP_PROJECT_ID` + `BQ_DATASET_RAW` are the dev/prod switch.
"""

import os
from datetime import datetime, timezone

from dagster import (
    AssetExecutionContext,
    Backoff,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    asset,
)
from google.cloud import bigquery

from .fetch import fetch_traffic_speed_bands

SOURCE_NAME = "traffic_speed_bands"

# Generic raw schema, reused by every source. payload is a real JSON column (lesson #22:
# pass the Python object, never json.dumps, or it lands double-encoded as a string).
RAW_SCHEMA = [
    bigquery.SchemaField("batch_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("payload", "JSON", mode="REQUIRED"),
]


@asset(
    name=SOURCE_NAME,
    group_name="ingestion",
    description="LTA TrafficSpeedBands snapshot landed opaquely (whole payload) into raw.",
    # A transient DNS/connection blip on a scheduled tick would lose that snapshot; ride
    # it out within the run (same stance as ev_charger_availability). Dagster does not
    # back-fill missed cron boundaries, so in-run retry is the only per-tick safety net.
    retry_policy=RetryPolicy(max_retries=3, delay=10, backoff=Backoff.EXPONENTIAL),
)
def traffic_speed_bands(context: AssetExecutionContext) -> MaterializeResult:
    api_key = os.environ["LTA_API_KEY"]
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["BQ_DATASET_RAW"]

    batch_id = context.run.run_id
    snapshot = fetch_traffic_speed_bands(api_key)
    row = {
        "batch_id": batch_id,
        "source_name": SOURCE_NAME,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "payload": snapshot,  # raw object, passed through untouched
    }

    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{SOURCE_NAME}"
    job = client.load_table_from_json(
        [row],
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=RAW_SCHEMA,
            write_disposition="WRITE_APPEND",
            # create_disposition defaults to CREATE_IF_NEEDED — table made on first run.
        ),
    )
    job.result()  # block; raises if the load failed (nothing partial lands)

    return MaterializeResult(
        metadata={
            "batch_id": MetadataValue.text(batch_id),
            "source_name": MetadataValue.text(SOURCE_NAME),
            "table": MetadataValue.text(table_id),
            # display-only freshness/size signal; not persisted as a column
            "payload_records": len(snapshot.get("value", [])),
        }
    )
