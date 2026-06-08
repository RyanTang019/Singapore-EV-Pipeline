"""Dagster asset: EVCBatch snapshot -> ONE opaque raw row -> BigQuery (WRITE_APPEND).

The VM does not reshape data. It fetches (envelope-validated), wraps the untouched
response in a single generic row `{batch_id, source_name, ingested_at, payload}`, and
appends it. All unnesting/exploding moves to dbt (in-warehouse). The 4-column schema is
defined here in code; the load job creates the table on first run via CREATE_IF_NEEDED,
so no Terraform owns the raw table. `GCP_PROJECT_ID` + `BQ_DATASET_RAW` are the dev/prod
switch.
"""

import os
from datetime import datetime, timezone

from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset
from google.cloud import bigquery

from .fetch import fetch_snapshot

SOURCE_NAME = "ev_charger_availability"

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
    description="LTA EVCBatch snapshot landed opaquely (whole payload) into raw.",
)
def ev_charger_availability(context: AssetExecutionContext) -> MaterializeResult:
    api_key = os.environ["LTA_API_KEY"]
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["BQ_DATASET_RAW"]

    batch_id = context.run.run_id
    snapshot = fetch_snapshot(api_key)
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
            "payload_locations": len(snapshot.get("evLocationsData", [])),
        }
    )
