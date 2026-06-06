"""Pure transform: an EVCBatch snapshot dict -> list of grain-B row dicts.

No network, no clock, no BigQuery — every fact needed to build a row is passed in,
so this module holds all the bug-prone logic in a trivially testable form.
"""

from datetime import datetime, timezone

# Keys every location must carry (verified against the live payload). The coordinate
# field is misspelled `longtitude` in the API — read it with the API's spelling.
REQUIRED_LOCATION_KEYS = (
    "address",
    "name",
    "postalCode",
    "latitude",
    "longtitude",
    "chargingPoints",
)


def _parse_last_updated(raw: str) -> datetime:
    """Parse the snapshot's `"YYYY-MM-DD HH:MM:SS"` timestamp as UTC-aware."""
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def snapshot_to_rows(snapshot: dict, ingested_at: datetime) -> list[dict]:
    """Reshape an EVCBatch snapshot into one BigQuery row per location (grain B).

    `chargingPoints` is kept as a JSON string (not flattened), so the nested tree —
    including the undocumented `"100"` status — survives to dbt. `ingested_at` is
    injected (not read from the clock here) so the function stays deterministic and
    every row in a run shares one timestamp.

    Raises ValueError on an empty/missing `evLocationsData` (a real snapshot has
    thousands; zero means upstream breakage, and writing zero rows would corrupt the
    append-only history). Raises KeyError, naming the record, if a location is missing
    an expected key (so a payload-shape change fails loud instead of NULLing a column).
    """
    locations = snapshot.get("evLocationsData")
    if not locations:
        raise ValueError(
            "evLocationsData is empty or missing — refusing to write zero rows"
        )

    last_updated_time = _parse_last_updated(snapshot["LastUpdatedTime"]).isoformat()
    ingested_at_iso = ingested_at.isoformat()

    rows: list[dict] = []
    for index, loc in enumerate(locations):
        missing = [k for k in REQUIRED_LOCATION_KEYS if k not in loc]
        if missing:
            raise KeyError(
                f"location index {index} (name={loc.get('name')!r}) "
                f"missing keys: {missing}"
            )
        rows.append(
            {
                "address": loc["address"],
                "name": loc["name"],
                "postal_code": loc["postalCode"],
                "latitude": float(loc["latitude"]),
                "longitude": float(loc["longtitude"]),  # API typo -> correct column
                # Pass the object through; the BigQuery client serializes the JSON
                # column once. (json.dumps here would double-encode -> stored as a
                # JSON *string* instead of an array, breaking charging_points[0].)
                "charging_points": loc["chargingPoints"],
                "last_updated_time": last_updated_time,
                "ingested_at": ingested_at_iso,
            }
        )
    return rows
