from pathlib import Path
from unittest.mock import patch

import orchestrate
from dagster import Backoff, load_from_defs_folder, materialize

ASSET_MOD = "orchestrate.defs.traffic_speed_bands.asset"

VALID_SNAPSHOT = {
    "lastUpdatedTime": "2026-06-11 10:00:00",
    "value": [{"LinkID": "103011995", "SpeedBand": 2}, {"LinkID": "103009235", "SpeedBand": 3}],
}


def test_asset_lands_one_opaque_row(monkeypatch):
    monkeypatch.setenv("LTA_API_KEY", "K")
    monkeypatch.setenv("GCP_PROJECT_ID", "sg-pipeline-dev")
    monkeypatch.setenv("BQ_DATASET_RAW", "dev_raw")

    from orchestrate.defs.traffic_speed_bands.asset import traffic_speed_bands

    # Materialize through the real Dagster path (real run_id). Patch only the fetch and
    # the BigQuery *client* (the network boundaries); the real LoadJobConfig is built.
    with patch(f"{ASSET_MOD}.fetch_traffic_speed_bands", return_value=VALID_SNAPSHOT), patch(
        f"{ASSET_MOD}.bigquery.Client"
    ) as client_cls:
        client = client_cls.return_value
        result = materialize([traffic_speed_bands])

    assert result.success
    args, kwargs = client.load_table_from_json.call_args

    # Exactly one opaque row with the 4 generic columns.
    rows = args[0]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"batch_id", "source_name", "ingested_at", "payload"}
    assert row["batch_id"] == result.run_id
    assert row["source_name"] == "traffic_speed_bands"
    # payload passed through untouched (NOT json.dumps'd) so the JSON column lands as a
    # real object, not a double-encoded string (PROJECT_CONTEXT lesson #22).
    assert row["payload"] is VALID_SNAPSHOT

    # Appends to the env-derived table, with the explicit 4-column schema so the table
    # is created (CREATE_IF_NEEDED) on first run.
    assert args[1] == "sg-pipeline-dev.dev_raw.traffic_speed_bands"
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
    # A transient DNS/connection blip on a scheduled tick would lose that snapshot, so
    # the asset carries a RetryPolicy (same durability stance as ev_charger_availability).
    from orchestrate.defs.traffic_speed_bands.asset import traffic_speed_bands

    policy = traffic_speed_bands.op.retry_policy
    assert policy is not None
    assert policy.max_retries == 3
    assert policy.delay == 10
    assert policy.backoff == Backoff.EXPONENTIAL


def test_asset_is_discovered_by_defs_folder():
    root = Path(orchestrate.__file__).parent  # src/orchestrate/
    defs = load_from_defs_folder(path_within_project=root)
    keys = defs.resolve_asset_graph().get_all_asset_keys()
    names = {key.path[-1] for key in keys}
    assert "traffic_speed_bands" in names
