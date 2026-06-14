import pytest

from orchestrate.defs.ingestion.extractors import json_path_array


def test_json_path_array_returns_top_level_key():
    assert json_path_array({"value": [1, 2, 3]}, "$.value") == [1, 2, 3]


def test_json_path_array_other_key():
    assert json_path_array({"evLocationsData": [{"a": 1}]}, "$.evLocationsData") == [{"a": 1}]


def test_json_path_array_missing_key_is_empty():
    assert json_path_array({}, "$.value") == []


def test_json_path_array_rejects_non_dollar_path():
    with pytest.raises(ValueError):
        json_path_array({"value": []}, "value")


def test_json_path_array_rejects_nested_path():
    with pytest.raises(ValueError):
        json_path_array({"a": {"b": []}}, "$.a.b")


from unittest.mock import MagicMock, patch

from orchestrate.defs.ingestion.extractors import ODataPagedExtractor

GET = "orchestrate.defs.ingestion.extractors.requests.get"
ODATA_URL = "https://example/odata"


def _page(records, last_updated=None):
    """A mocked OData page. Includes lastUpdatedTime only when given (traffic has it,
    carpark does not)."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    body = {"odata.metadata": "https://example/$metadata", "value": records}
    if last_updated is not None:
        body["lastUpdatedTime"] = last_updated
    m.json.return_value = body
    return m


def test_odata_accumulates_all_pages_and_stops_on_empty():
    pages = [_page([1, 2]), _page([3, 4]), _page([])]
    with patch(GET, side_effect=pages):
        out = ODataPagedExtractor(ODATA_URL).extract("MYKEY")
    assert out["value"] == [1, 2, 3, 4]


def test_odata_skip_advances_by_page_length_not_a_hardcoded_step():
    pages = [_page([1, 2]), _page([3, 4]), _page([])]
    with patch(GET, side_effect=pages) as g:
        ODataPagedExtractor(ODATA_URL).extract("MYKEY")
    skips = [call.kwargs["params"]["$skip"] for call in g.call_args_list]
    assert skips == [0, 2, 4]
    assert all(c.kwargs["headers"]["AccountKey"] == "MYKEY" for c in g.call_args_list)


def test_odata_advances_by_length_on_partial_final_page():
    pages = [_page([1, 2]), _page([3]), _page([])]
    with patch(GET, side_effect=pages) as g:
        out = ODataPagedExtractor(ODATA_URL).extract("MYKEY")
    assert out["value"] == [1, 2, 3]
    skips = [call.kwargs["params"]["$skip"] for call in g.call_args_list]
    assert skips == [0, 2, 3]


def test_odata_keeps_last_updated_time_from_first_page_when_present():
    pages = [
        _page([1, 2], last_updated="2026-06-11 10:00:00"),
        _page([3], last_updated="2026-06-11 10:05:00"),
        _page([]),
    ]
    with patch(GET, side_effect=pages):
        out = ODataPagedExtractor(ODATA_URL).extract("MYKEY")
    assert out["lastUpdatedTime"] == "2026-06-11 10:00:00"


def test_odata_omits_stamp_when_source_has_none():
    # CarParkAvailabilityv2 carries no lastUpdatedTime — the reassembled payload must NOT
    # fabricate one; it is value-only.
    pages = [_page([{"CarParkID": "2"}]), _page([])]
    with patch(GET, side_effect=pages):
        out = ODataPagedExtractor(ODATA_URL).extract("MYKEY")
    assert set(out) == {"value"}


def test_odata_empty_result_raises():
    with patch(GET, side_effect=[_page([])]):
        with pytest.raises(ValueError):
            ODataPagedExtractor(ODATA_URL).extract("MYKEY")


from orchestrate.defs.ingestion.extractors import S3LinkExtractor

META_URL = "https://example/EVCBatch"


def _resp(json_data, raise_exc=None):
    m = MagicMock()
    m.raise_for_status.side_effect = raise_exc
    m.json.return_value = json_data
    return m


def test_s3_two_step_reads_link_then_downloads():
    link_resp = _resp({"value": [{"Link": "https://s3.example/snap"}]})
    snap_resp = _resp({"LastUpdatedTime": "2026-06-02 15:25:00", "evLocationsData": [1]})
    with patch(GET, side_effect=[link_resp, snap_resp]) as g:
        out = S3LinkExtractor(META_URL).extract("MYKEY")
    assert out["evLocationsData"] == [1]
    assert g.call_args_list[0].kwargs["headers"]["AccountKey"] == "MYKEY"
    assert g.call_args_list[1].args[0] == "https://s3.example/snap"


def test_s3_expired_link_retries_once_then_succeeds():
    import requests
    link1 = _resp({"value": [{"Link": "https://s3.example/expired"}]})
    download_fail = _resp({}, raise_exc=requests.HTTPError("403 expired"))
    link2 = _resp({"value": [{"Link": "https://s3.example/fresh"}]})
    snap = _resp({"LastUpdatedTime": "2026-06-02 15:25:00", "evLocationsData": [1]})
    with patch(GET, side_effect=[link1, download_fail, link2, snap]):
        out = S3LinkExtractor(META_URL).extract("MYKEY")
    assert out["evLocationsData"] == [1]


def test_s3_download_failing_twice_raises():
    import requests
    link1 = _resp({"value": [{"Link": "https://s3.example/a"}]})
    fail1 = _resp({}, raise_exc=requests.HTTPError("403"))
    link2 = _resp({"value": [{"Link": "https://s3.example/b"}]})
    fail2 = _resp({}, raise_exc=requests.HTTPError("403"))
    with patch(GET, side_effect=[link1, fail1, link2, fail2]):
        with pytest.raises(requests.HTTPError):
            S3LinkExtractor(META_URL).extract("MYKEY")


def test_s3_step1_failure_raises_without_retry():
    import requests
    fail = _resp({}, raise_exc=requests.HTTPError("401 bad key"))
    with patch(GET, side_effect=[fail]) as g:
        with pytest.raises(requests.HTTPError):
            S3LinkExtractor(META_URL).extract("MYKEY")
    assert g.call_count == 1


@pytest.mark.parametrize("empty", [{}, []])
def test_s3_empty_payload_raises(empty):
    link = _resp({"value": [{"Link": "https://s3.example/snap"}]})
    snap = _resp(empty)
    with patch(GET, side_effect=[link, snap]):
        with pytest.raises(ValueError):
            S3LinkExtractor(META_URL).extract("MYKEY")
