from unittest.mock import patch

from orchestrate.defs.ingestion.landing import load_raw

LANDING = "orchestrate.defs.ingestion.landing"
PAYLOAD = {"value": [{"a": 1}, {"a": 2}]}


def test_load_raw_lands_one_opaque_row_and_returns_table_id():
    with patch(f"{LANDING}.bigquery.Client") as client_cls:
        client = client_cls.return_value
        table_id = load_raw(
            "carpark_availability",
            PAYLOAD,
            batch_id="run-123",
            project="sg-pipeline-dev",
            dataset="dev_raw",
        )

    assert table_id == "sg-pipeline-dev.dev_raw.carpark_availability"
    args, kwargs = client.load_table_from_json.call_args

    rows = args[0]
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"batch_id", "source_name", "ingested_at", "payload"}
    assert row["batch_id"] == "run-123"
    assert row["source_name"] == "carpark_availability"
    # payload passed through untouched (lesson #22: not json.dumps'd).
    assert row["payload"] is PAYLOAD

    assert args[1] == "sg-pipeline-dev.dev_raw.carpark_availability"
    assert kwargs["job_config"].write_disposition == "WRITE_APPEND"
    schema = {f.name: f.field_type for f in kwargs["job_config"].schema}
    assert schema == {
        "batch_id": "STRING",
        "source_name": "STRING",
        "ingested_at": "TIMESTAMP",
        "payload": "JSON",
    }
    # blocks on the load job so nothing partial lands.
    client.load_table_from_json.return_value.result.assert_called_once()
