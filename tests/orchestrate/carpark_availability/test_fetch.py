from unittest.mock import MagicMock, patch

import pytest

from orchestrate.defs.carpark_availability.fetch import fetch_carpark_availability

GET = "orchestrate.defs.carpark_availability.fetch.requests.get"


def _page(records):
    """A mocked OData page response: {odata.metadata, value}. No lastUpdatedTime."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {"odata.metadata": "https://example/$metadata", "value": records}
    return m


def test_accumulates_all_pages_and_stops_on_empty():
    pages = [_page([1, 2]), _page([3, 4]), _page([])]
    with patch(GET, side_effect=pages):
        out = fetch_carpark_availability("MYKEY")

    assert out["value"] == [1, 2, 3, 4]


def test_payload_is_value_only_no_snapshot_stamp():
    # CarParkAvailabilityv2 has no top-level lastUpdatedTime (unlike TrafficSpeedBands),
    # so the reassembled payload carries only the value array.
    pages = [_page([{"CarParkID": "2"}]), _page([])]
    with patch(GET, side_effect=pages):
        out = fetch_carpark_availability("MYKEY")

    assert set(out) == {"value"}


def test_skip_advances_by_page_length_not_a_hardcoded_step():
    pages = [_page([1, 2]), _page([3, 4]), _page([])]
    with patch(GET, side_effect=pages) as g:
        fetch_carpark_availability("MYKEY")

    skips = [call.kwargs["params"]["$skip"] for call in g.call_args_list]
    assert skips == [0, 2, 4]
    assert all(call.kwargs["headers"]["AccountKey"] == "MYKEY" for call in g.call_args_list)


def test_advances_by_length_on_a_partial_final_page():
    pages = [_page([1, 2]), _page([3]), _page([])]
    with patch(GET, side_effect=pages) as g:
        out = fetch_carpark_availability("MYKEY")

    assert out["value"] == [1, 2, 3]
    skips = [call.kwargs["params"]["$skip"] for call in g.call_args_list]
    assert skips == [0, 2, 3]


def test_empty_result_raises_and_lands_nothing():
    with patch(GET, side_effect=[_page([])]):
        with pytest.raises(ValueError):
            fetch_carpark_availability("MYKEY")
