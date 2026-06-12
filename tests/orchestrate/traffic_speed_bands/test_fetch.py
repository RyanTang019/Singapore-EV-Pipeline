from unittest.mock import MagicMock, patch

import pytest

from orchestrate.defs.traffic_speed_bands.fetch import fetch_traffic_speed_bands

GET = "orchestrate.defs.traffic_speed_bands.fetch.requests.get"


def _page(records, last_updated="2026-06-11 10:00:00"):
    """A mocked OData page response: {odata.metadata, lastUpdatedTime, value}."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "odata.metadata": "https://example/$metadata",
        "lastUpdatedTime": last_updated,
        "value": records,
    }
    return m


def test_accumulates_all_pages_and_stops_on_empty():
    # Two full pages of 2, then an empty page signals the end.
    pages = [_page([1, 2]), _page([3, 4]), _page([])]
    with patch(GET, side_effect=pages):
        out = fetch_traffic_speed_bands("MYKEY")

    # Every record across the pages is assembled into one reassembled envelope.
    assert out["value"] == [1, 2, 3, 4]


def test_skip_advances_by_page_length_not_a_hardcoded_step():
    # The $skip step MUST equal the page size the endpoint returns (500 live), NOT the
    # stale "increment by 50" convention. Proven here with size-2 pages: skip walks
    # 0 -> 2 -> 4 (by len(page)), never 0 -> 50 -> 100.
    pages = [_page([1, 2]), _page([3, 4]), _page([])]
    with patch(GET, side_effect=pages) as g:
        fetch_traffic_speed_bands("MYKEY")

    skips = [call.kwargs["params"]["$skip"] for call in g.call_args_list]
    assert skips == [0, 2, 4]
    # AccountKey header carried on every call.
    assert all(call.kwargs["headers"]["AccountKey"] == "MYKEY" for call in g.call_args_list)


def test_advances_by_length_on_a_partial_final_page():
    # A short final page (1 record) must advance skip by 1, not by a fixed step, so the
    # terminating empty fetch lands at the correct offset.
    pages = [_page([1, 2]), _page([3]), _page([])]
    with patch(GET, side_effect=pages) as g:
        out = fetch_traffic_speed_bands("MYKEY")

    assert out["value"] == [1, 2, 3]
    skips = [call.kwargs["params"]["$skip"] for call in g.call_args_list]
    assert skips == [0, 2, 3]


def test_preserves_last_updated_time_from_first_page():
    # Like EVCBatch's LastUpdatedTime, the snapshot stamp is kept inside the payload so
    # dbt can extract it; taken from the first page.
    pages = [
        _page([1, 2], last_updated="2026-06-11 10:00:00"),
        _page([3], last_updated="2026-06-11 10:05:00"),
        _page([]),
    ]
    with patch(GET, side_effect=pages):
        out = fetch_traffic_speed_bands("MYKEY")

    assert out["lastUpdatedTime"] == "2026-06-11 10:00:00"


def test_empty_result_raises_and_lands_nothing():
    # Envelope guard (Option A): zero records assembled must raise so an empty payload
    # never lands on the append-only raw table.
    with patch(GET, side_effect=[_page([])]):
        with pytest.raises(ValueError):
            fetch_traffic_speed_bands("MYKEY")
