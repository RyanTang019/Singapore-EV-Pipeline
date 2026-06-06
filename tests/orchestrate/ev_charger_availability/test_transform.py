import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orchestrate.defs.ev_charger_availability.transform import snapshot_to_rows

FIXTURE = Path(__file__).parent / "fixtures" / "evbatch_sample.json"
INGESTED = datetime(2026, 6, 2, 16, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def snapshot():
    return json.loads(FIXTURE.read_text())


def test_one_row_per_location(snapshot):
    rows = snapshot_to_rows(snapshot, INGESTED)
    assert len(rows) == len(snapshot["evLocationsData"]) == 3


def test_longitude_is_nonnull_float(snapshot):
    # Guards the API's `longtitude` misspelling — a wrong read would NULL the column.
    rows = snapshot_to_rows(snapshot, INGESTED)
    assert all(isinstance(r["longitude"], float) for r in rows)
    assert rows[0]["longitude"] == 103.959758


def test_charging_points_kept_as_object_with_status_100(snapshot):
    # charging_points is passed through as a Python list (NOT json.dumps'd) so the
    # BigQuery JSON column lands as an array, not a double-encoded string.
    rows = snapshot_to_rows(snapshot, INGESTED)
    assert isinstance(rows[0]["charging_points"], list)
    seen = {cp["status"] for r in rows for cp in r["charging_points"]}
    assert "100" in seen  # grain B preserves the undocumented OOS status verbatim


def test_last_updated_time_parsed(snapshot):
    rows = snapshot_to_rows(snapshot, INGESTED)
    assert rows[0]["last_updated_time"] == "2026-06-02T15:25:00+00:00"


def test_ingested_at_injected_on_every_row(snapshot):
    rows = snapshot_to_rows(snapshot, INGESTED)
    assert all(r["ingested_at"] == INGESTED.isoformat() for r in rows)


def test_empty_locations_raises():
    with pytest.raises(ValueError):
        snapshot_to_rows(
            {"LastUpdatedTime": "2026-06-02 15:25:00", "evLocationsData": []},
            INGESTED,
        )


def test_location_missing_key_raises_naming_record(snapshot):
    snapshot["evLocationsData"][0].pop("address")
    with pytest.raises(KeyError) as exc:
        snapshot_to_rows(snapshot, INGESTED)
    assert "Normal Carpark" in str(exc.value)  # error names the offending record
