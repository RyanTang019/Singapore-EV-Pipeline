from unittest.mock import MagicMock, patch

import pytest
import requests

from orchestrate.defs.ev_charger_availability.fetch import fetch_snapshot

GET = "orchestrate.defs.ev_charger_availability.fetch.requests.get"


def _resp(json_data, raise_exc=None):
    m = MagicMock()
    m.raise_for_status.side_effect = raise_exc
    m.json.return_value = json_data
    return m


def test_two_step_fetch_reads_link_then_downloads():
    link_resp = _resp({"value": [{"Link": "https://s3.example/snap"}]})
    snap_resp = _resp({"LastUpdatedTime": "2026-06-02 15:25:00", "evLocationsData": [1]})
    with patch(GET, side_effect=[link_resp, snap_resp]) as g:
        out = fetch_snapshot("MYKEY")

    assert out["evLocationsData"] == [1]
    # step 1: EVCBatch with the AccountKey header
    assert g.call_args_list[0].kwargs["headers"]["AccountKey"] == "MYKEY"
    # step 2: GET the pre-signed link returned by step 1
    assert g.call_args_list[1].args[0] == "https://s3.example/snap"


def test_expired_link_retries_once_then_succeeds():
    link1 = _resp({"value": [{"Link": "https://s3.example/expired"}]})
    download_fail = _resp({}, raise_exc=requests.HTTPError("403 expired"))
    link2 = _resp({"value": [{"Link": "https://s3.example/fresh"}]})
    snap = _resp({"LastUpdatedTime": "2026-06-02 15:25:00", "evLocationsData": [1]})
    with patch(GET, side_effect=[link1, download_fail, link2, snap]):
        out = fetch_snapshot("MYKEY")
    assert out["evLocationsData"] == [1]


def test_download_failing_twice_raises():
    link1 = _resp({"value": [{"Link": "https://s3.example/a"}]})
    fail1 = _resp({}, raise_exc=requests.HTTPError("403"))
    link2 = _resp({"value": [{"Link": "https://s3.example/b"}]})
    fail2 = _resp({}, raise_exc=requests.HTTPError("403"))
    with patch(GET, side_effect=[link1, fail1, link2, fail2]):
        with pytest.raises(requests.HTTPError):
            fetch_snapshot("MYKEY")


def test_step1_failure_raises_without_retry():
    fail = _resp({}, raise_exc=requests.HTTPError("401 bad key"))
    with patch(GET, side_effect=[fail]) as g:
        with pytest.raises(requests.HTTPError):
            fetch_snapshot("MYKEY")
    assert g.call_count == 1  # no blind retry against a bad key
