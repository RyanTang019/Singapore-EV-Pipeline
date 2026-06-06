from pathlib import Path
from unittest.mock import patch

import orchestrate
from dagster import load_from_defs_folder

ASSET_MOD = "orchestrate.defs.ev_charger_availability.asset"

VALID_SNAPSHOT = {
    "LastUpdatedTime": "2026-06-02 15:25:00",
    "evLocationsData": [
        {
            "address": "1 Test Road",
            "name": "Test Carpark",
            "longtitude": 103.95,
            "latitude": 1.36,
            "postalCode": "123456",
            "chargingPoints": [{"status": "1", "plugTypes": []}],
        }
    ],
}


def test_asset_loads_with_write_append_to_env_table(monkeypatch):
    monkeypatch.setenv("LTA_API_KEY", "K")
    monkeypatch.setenv("GCP_PROJECT_ID", "sg-pipeline-dev")
    monkeypatch.setenv("BQ_DATASET_RAW", "dev_raw")

    from orchestrate.defs.ev_charger_availability.asset import ev_charger_availability

    # Patch only the BigQuery *client* (the network boundary) so the real
    # LoadJobConfig is constructed and its write_disposition is a real value.
    with patch(f"{ASSET_MOD}.fetch_snapshot", return_value=VALID_SNAPSHOT), patch(
        f"{ASSET_MOD}.bigquery.Client"
    ) as client_cls:
        client = client_cls.return_value
        result = ev_charger_availability()

    args, kwargs = client.load_table_from_json.call_args
    assert args[1] == "sg-pipeline-dev.dev_raw.ev_charger_availability"
    assert kwargs["job_config"].write_disposition == "WRITE_APPEND"
    client.load_table_from_json.return_value.result.assert_called_once()
    assert result.metadata["num_locations"] == 1


def test_asset_is_discovered_by_defs_folder():
    root = Path(orchestrate.__file__).parent  # src/orchestrate/
    defs = load_from_defs_folder(path_within_project=root)
    keys = defs.resolve_asset_graph().get_all_asset_keys()
    names = {key.path[-1] for key in keys}
    assert "ev_charger_availability" in names
