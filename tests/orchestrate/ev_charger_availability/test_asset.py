from pathlib import Path
from unittest.mock import patch

import orchestrate
from dagster import Backoff, load_from_defs_folder, materialize

ASSET_MOD = "orchestrate.defs.ev_charger_availability.asset"

VALID_SNAPSHOT = {
    "LastUpdatedTime": "2026-06-02 15:25:00",
    "evLocationsData": [{"address": "1 Test Road", "chargingPoints": []}],
}


def test_asset_lands_one_opaque_row(monkeypatch):
    monkeypatch.setenv("LTA_API_KEY", "K")
    monkeypatch.setenv("GCP_PROJECT_ID", "sg-pipeline-dev")
    monkeypatch.setenv("BQ_DATASET_RAW", "dev_raw")

    from orchestrate.defs.ev_charger_availability.asset import ev_charger_availability

    # Materialize through the real Dagster execution path (so context.run.run_id is a
    # real run id). Patch only the BigQuery *client* (the network boundary) so the real
    # LoadJobConfig is constructed and its schema/write_disposition are real values.
    with patch(f"{ASSET_MOD}.fetch_snapshot", return_value=VALID_SNAPSHOT), patch(
        f"{ASSET_MOD}.bigquery.Client"
    ) as client_cls:
        client = client_cls.return_value
        result = materialize([ev_charger_availability])

    assert result.success
    args, kwargs = client.load_table_from_json.call_args

    # Exactly one opaque row with the 4 generic columns.
    rows = args[0]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"batch_id", "source_name", "ingested_at", "payload"}
    assert row["batch_id"] == result.run_id
    assert row["source_name"] == "ev_charger_availability"
    # payload passed through untouched (NOT json.dumps'd) so the JSON column lands as a
    # real object, not a double-encoded string (PROJECT_CONTEXT lesson #22).
    assert row["payload"] is VALID_SNAPSHOT

    # Appends to the env-derived table, with the explicit 4-column schema so the table
    # is created (CREATE_IF_NEEDED) on first run.
    assert args[1] == "sg-pipeline-dev.dev_raw.ev_charger_availability"
    assert kwargs["job_config"].write_disposition == "WRITE_APPEND"
    schema = {f.name: f.field_type for f in kwargs["job_config"].schema}
    assert schema == {
        "batch_id": "STRING",
        "source_name": "STRING",
        "ingested_at": "TIMESTAMP",
        "payload": "JSON",
    }
    client.load_table_from_json.return_value.result.assert_called_once()


def test_asset_retries_on_transient_failure():
    # EVCBatch is unrecoverable (5-min S3 expiry, no history endpoint), so a transient
    # network/DNS blip on a scheduled tick loses that snapshot forever. The asset carries
    # a RetryPolicy to ride out the blip within the same run.
    from orchestrate.defs.ev_charger_availability.asset import ev_charger_availability

    policy = ev_charger_availability.op.retry_policy
    assert policy is not None
    assert policy.max_retries == 3
    assert policy.delay == 10
    assert policy.backoff == Backoff.EXPONENTIAL


def test_asset_is_discovered_by_defs_folder():
    root = Path(orchestrate.__file__).parent  # src/orchestrate/
    defs = load_from_defs_folder(path_within_project=root)
    keys = defs.resolve_asset_graph().get_all_asset_keys()
    names = {key.path[-1] for key in keys}
    assert "ev_charger_availability" in names
