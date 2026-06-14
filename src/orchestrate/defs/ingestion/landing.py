"""Shared opaque-raw landing function: one row {batch_id, source_name, ingested_at, payload}
per run, WRITE_APPEND into BigQuery. Pulled out of the (formerly duplicated) per-source
assets — the only per-source value is source_name. RAW_SCHEMA lives here as the single
definition (was copy-pasted in all three assets).
"""

from datetime import datetime, timezone

from google.cloud import bigquery

# Generic raw schema, reused by every source. payload is a real JSON column (lesson #22:
# pass the Python object, never json.dumps, or it lands double-encoded as a string).
RAW_SCHEMA = [
    bigquery.SchemaField("batch_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("payload", "JSON", mode="REQUIRED"),
]


def load_raw(
    source_name: str,
    payload: dict,
    *,
    batch_id: str,
    project: str,
    dataset: str,
) -> str:
    """Land one opaque row via WRITE_APPEND / CREATE_IF_NEEDED; block on the job; return the
    table_id. Reused by every source; the only per-source value is source_name."""
    row = {
        "batch_id": batch_id,
        "source_name": source_name,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,  # raw object, passed through untouched
    }
    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{source_name}"
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
    return table_id
