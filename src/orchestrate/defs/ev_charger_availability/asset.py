"""Dagster asset: EVCBatch snapshot -> grain-B rows -> BigQuery (WRITE_APPEND).

Thin glue only. The bug-prone logic lives in `transform.py` (pure) and `fetch.py`
(I/O); this module reads env config, stamps one `ingested_at` for the run, and
runs an atomic load job. `GCP_PROJECT_ID` + `BQ_DATASET_RAW` are the dev/prod
switch: `sg-pipeline-dev` + shared `dev_raw` locally, prod project + `prod_raw`
on the VM.
"""

import os
from datetime import datetime, timezone

from dagster import MaterializeResult, MetadataValue, asset
from google.cloud import bigquery

from .fetch import fetch_snapshot
from .transform import snapshot_to_rows


@asset(
    name="ev_charger_availability",
    group_name="ingestion",
    description="LTA EVCBatch snapshot -> grain B (one row per location), appended to raw.",
)
def ev_charger_availability() -> MaterializeResult:
    api_key = os.environ["LTA_API_KEY"]
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["BQ_DATASET_RAW"]

    ingested_at = datetime.now(timezone.utc)
    snapshot = fetch_snapshot(api_key)
    rows = snapshot_to_rows(snapshot, ingested_at)

    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.ev_charger_availability"
    job = client.load_table_from_json(
        rows,
        table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    )
    job.result()  # block; raises if the load failed (nothing partial lands)

    return MaterializeResult(
        metadata={
            "num_locations": len(rows),
            "last_updated_time": MetadataValue.text(str(snapshot["LastUpdatedTime"])),
            "table": MetadataValue.text(table_id),
        }
    )
