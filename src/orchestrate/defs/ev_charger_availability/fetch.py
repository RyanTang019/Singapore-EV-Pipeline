"""EVCBatch 2-step fetch (network I/O only).

LTA's EVCBatch endpoint returns metadata containing a pre-signed S3 link that
expires in ~5 minutes; the actual snapshot is downloaded from that link. The link
TTL is the one expected transient failure, so a failed download is retried once
with a fresh link. A step-1 failure (bad key, network) is NOT retried.
"""

import requests

EVCBATCH_URL = "https://datamall2.mytransport.sg/ltaodataservice/EVCBatch"
TIMEOUT_SECONDS = 30


def fetch_snapshot(api_key: str) -> dict:
    """Return the raw EVCBatch snapshot dict (`{LastUpdatedTime, evLocationsData}`)."""
    link = _request_link(api_key)
    try:
        return _download(link)
    except requests.RequestException:
        # Expired link is expected; get a fresh one and retry the download once.
        link = _request_link(api_key)
        return _download(link)


def _request_link(api_key: str) -> str:
    resp = requests.get(
        EVCBATCH_URL,
        headers={"AccountKey": api_key},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["value"][0]["Link"]


def _download(link: str) -> dict:
    resp = requests.get(link, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()
