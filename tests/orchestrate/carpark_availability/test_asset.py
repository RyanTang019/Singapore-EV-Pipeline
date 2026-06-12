from pathlib import Path
from unittest.mock import patch

import orchestrate
from dagster import Backoff, load_from_defs_folder, materialize

ASSET_MOD = "orchestrate.defs.carpark_availability.asset"

VALID_SNAPSHOT = {
    "value": [
        {"CarParkID": "2", "AvailableLots": 1321},
        {"CarParkID": "3", "AvailableLots": 50},
    ],
}


def test_asset_lands_one_opaque_row(monkeypatch):
    monkeypatch.setenv("LTA_API_KEY", "K")
    monkeypatch.setenv("GCP_PROJECT_ID", "sg-pipeline-dev")
    monkeypatch.setenv("BQ_DATASET_RAW", "dev_raw")

    from orchestrate.defs.carpark_availability.asset import carpark_availability

    with patch(f"{ASSET_MOD}.fetch_carpark_availability", return_value=VALID_SNAPSHOT), patch(
        f"{ASSET_MOD}.bigquery.Client"
    ) as client_cls:
        client = client_cls.return_value
        result = materialize([carpark_availability])

    assert result.success
    args, kwargs = client.load_table_from_json.call_args

    rows = args[0]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"batch_id", "source_name", "ingested_at", "payload"}
    assert row["batch_id"] == result.run_id
    assert row["source_name"] == "carpark_availability"
    assert row["payload"] is VALID_SNAPSHOT

    assert args[1] == "sg-pipeline-dev.dev_raw.carpark_availability"
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
    from orchestrate.defs.carpark_availability.asset import carpark_availability

    policy = carpark_availability.op.retry_policy
    assert policy is not None
    assert policy.max_retries == 3
    assert policy.delay == 10
    assert policy.backoff == Backoff.EXPONENTIAL


def test_asset_is_discovered_by_defs_folder():
    root = Path(orchestrate.__file__).parent
    defs = load_from_defs_folder(path_within_project=root)
    keys = defs.resolve_asset_graph().get_all_asset_keys()
    names = {key.path[-1] for key in keys}
    assert "carpark_availability" in names
