"""CarParkAvailability fetch (network I/O only).

LTA's `CarParkAvailabilityv2` is a paginated OData GET: each call returns up to one page
of records under `value`. Unlike TrafficSpeedBands it carries NO top-level
`lastUpdatedTime`, so the reassembled payload is just `{value: [...]}` (the asset's
`ingested_at` column records the snapshot time). We walk `$skip` until an empty page,
accumulating every record into one payload so the asset lands ONE opaque row per run.

Page size is **500** live (verified 2026-06-12). The loop advances `$skip` by the number
of records each page actually returned, so it is correct whatever the page size is.
"""

import requests

CARPARK_AVAILABILITY_URL = (
    "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2"
)
TIMEOUT_SECONDS = 30


def fetch_carpark_availability(api_key: str) -> dict:
    """Return the reassembled snapshot `{value: [...all records...]}`.

    Envelope-validated only (Option A): `raise_for_status()` covers HTTP, `.json()`
    covers parse-ability, and the non-empty check below refuses to return a snapshot with
    zero records — so an empty payload never lands on the append-only raw table.
    """
    records: list = []
    skip = 0
    while True:
        page = _get_page(api_key, skip).get("value", [])
        if not page:  # empty page = past the end
            break
        records.extend(page)
        skip += len(page)  # advance by what this page returned, never a fixed step
    if not records:
        raise ValueError(
            "CarParkAvailability returned an empty payload — refusing to land"
        )
    return {"value": records}


def _get_page(api_key: str, skip: int) -> dict:
    resp = requests.get(
        CARPARK_AVAILABILITY_URL,
        headers={"AccountKey": api_key},
        params={"$skip": skip},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()
