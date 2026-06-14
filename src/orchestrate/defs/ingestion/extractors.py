"""Extractor drivers: how each source fetches its payload (network I/O only).

One Extractor per fetch *protocol*, not per source — the OData pair (traffic, carpark)
share ODataPagedExtractor, differing only by URL. Each extractor owns its Option-A
envelope guard (non-empty or raise) so an empty blob never lands on the append-only raw
table. No field/schema inspection here; that is dbt's job.
"""

from typing import Protocol

import requests

TIMEOUT_SECONDS = 30


class Extractor(Protocol):
    def extract(self, api_key: str) -> dict: ...


class ODataPagedExtractor:
    """LTA OData `$skip`-paginated GET. Walks pages until empty, accumulating every record
    into one reassembled {value: [...]} payload. Includes lastUpdatedTime ONLY if the first
    page carried one (traffic does, carpark does not), so the stamp is optional. Advances
    `$skip` by the number of records each page actually returned — correct whatever the live
    page size is (500 for both endpoints as of 2026-06), never a hardcoded step.
    """

    def __init__(self, url: str):
        self.url = url

    def extract(self, api_key: str) -> dict:
        records: list = []
        last_updated_time = None
        skip = 0
        while True:
            data = self._get_page(api_key, skip)
            page = data.get("value", [])
            if not page:  # empty page = past the end
                break
            if not records:  # first page only
                last_updated_time = data.get("lastUpdatedTime")
            records.extend(page)
            skip += len(page)
        if not records:
            raise ValueError(f"{self.url} returned an empty payload — refusing to land")
        payload = {"value": records}
        if last_updated_time is not None:
            payload["lastUpdatedTime"] = last_updated_time
        return payload

    def _get_page(self, api_key: str, skip: int) -> dict:
        resp = requests.get(
            self.url,
            headers={"AccountKey": api_key},
            params={"$skip": skip},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()


class S3LinkExtractor:
    """EVCBatch 2-step fetch: the metadata endpoint returns a ~5-min pre-signed S3 link,
    then the snapshot is downloaded from it. The link TTL is the one expected transient
    failure, so a failed download is retried ONCE with a fresh link. A step-1 failure (bad
    key, network) is NOT retried. Envelope-guarded (Option A): a parseable-but-empty
    download raises rather than landing on the append-only table.
    """

    def __init__(self, metadata_url: str):
        self.metadata_url = metadata_url

    def extract(self, api_key: str) -> dict:
        link = self._request_link(api_key)
        try:
            snapshot = self._download(link)
        except requests.RequestException:
            # Expired link is expected; get a fresh one and retry the download once.
            snapshot = self._download(self._request_link(api_key))
        if not snapshot:
            raise ValueError("EVCBatch returned an empty payload — refusing to land")
        return snapshot

    def _request_link(self, api_key: str) -> str:
        resp = requests.get(
            self.metadata_url, headers={"AccountKey": api_key}, timeout=TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        return resp.json()["value"][0]["Link"]

    def _download(self, link: str) -> dict:
        resp = requests.get(link, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
