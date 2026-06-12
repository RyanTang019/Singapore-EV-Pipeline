"""TrafficSpeedBands fetch (network I/O only).

LTA's `v3/TrafficSpeedBands` is a paginated OData GET: each call returns up to one
page of records under `value`, plus a top-level `lastUpdatedTime` snapshot stamp. We
walk `$skip` until an empty page, accumulating every record into a single reassembled
`{lastUpdatedTime, value}` payload so the asset lands ONE opaque row per run — the same
grain as EVCBatch.

Page size is **500** live (verified 2026-06-11), NOT the stale "increment by 50"
convention. The loop advances `$skip` by the number of records each page actually
returned, so it is correct whatever the page size is and robust to it changing.
"""

import requests

TRAFFIC_SPEED_BANDS_URL = (
    "https://datamall2.mytransport.sg/ltaodataservice/v3/TrafficSpeedBands"
)
TIMEOUT_SECONDS = 30


def fetch_traffic_speed_bands(api_key: str) -> dict:
    """Return the reassembled snapshot `{lastUpdatedTime, value:[...all records...]}`.

    Envelope-validated only (Option A): `raise_for_status()` covers HTTP, `.json()`
    covers parse-ability, and the non-empty check below refuses to return a snapshot
    with zero records — so an empty payload never lands on the append-only raw table.
    No field/schema inspection happens here; that is dbt's job.
    """
    records: list = []
    last_updated_time = None
    skip = 0
    while True:
        data = _get_page(api_key, skip)
        page = data.get("value", [])
        if not page:  # empty page = past the end
            break
        if last_updated_time is None:  # keep the first page's snapshot stamp
            last_updated_time = data.get("lastUpdatedTime")
        records.extend(page)
        skip += len(page)  # advance by what this page returned, never a fixed step
    if not records:
        raise ValueError(
            "TrafficSpeedBands returned an empty payload — refusing to land"
        )
    return {"lastUpdatedTime": last_updated_time, "value": records}


def _get_page(api_key: str, skip: int) -> dict:
    resp = requests.get(
        TRAFFIC_SPEED_BANDS_URL,
        headers={"AccountKey": api_key},
        params={"$skip": skip},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()
