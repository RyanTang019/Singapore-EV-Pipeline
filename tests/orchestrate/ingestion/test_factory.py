from dagster import Backoff

from orchestrate.defs.ingestion.manifest import (
    DEFAULT_CRON,
    MANIFEST,
    STANDARD_RETRY,
    SourceConfig,
)


def test_manifest_has_three_sources_with_unchanged_names():
    names = {c.name for c in MANIFEST}
    assert names == {
        "ev_charger_availability",
        "traffic_speed_bands",
        "carpark_availability",
    }


def test_manifest_records_paths():
    by_name = {c.name: c for c in MANIFEST}
    assert by_name["ev_charger_availability"].records_path == "$.evLocationsData"
    assert by_name["traffic_speed_bands"].records_path == "$.value"
    assert by_name["carpark_availability"].records_path == "$.value"


def test_all_sources_default_to_30_minute_cron():
    assert DEFAULT_CRON == "*/30 * * * *"
    assert all(c.cron == "*/30 * * * *" for c in MANIFEST)


def test_source_config_is_frozen():
    import dataclasses
    import pytest

    cfg = MANIFEST[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.name = "mutated"


def test_standard_retry_policy():
    assert STANDARD_RETRY.max_retries == 3
    assert STANDARD_RETRY.delay == 10
    assert STANDARD_RETRY.backoff == Backoff.EXPONENTIAL


from unittest.mock import patch

from dagster import materialize

from orchestrate.defs.ingestion.factory import build_ingestion_asset

LANDING = "orchestrate.defs.ingestion.landing"


class _StubExtractor:
    def __init__(self, payload):
        self._payload = payload

    def extract(self, api_key: str) -> dict:
        return self._payload


def _fake_cfg(payload):
    return SourceConfig("fake_source", _StubExtractor(payload), "$.value")


def test_factory_asset_fetches_via_extractor_and_lands(monkeypatch):
    monkeypatch.setenv("LTA_API_KEY", "K")
    monkeypatch.setenv("GCP_PROJECT_ID", "sg-pipeline-dev")
    monkeypatch.setenv("BQ_DATASET_RAW", "dev_raw")

    payload = {"value": [{"a": 1}, {"a": 2}, {"a": 3}]}
    asset_def = build_ingestion_asset(_fake_cfg(payload))

    with patch(f"{LANDING}.bigquery.Client") as client_cls:
        client = client_cls.return_value
        result = materialize([asset_def])

    assert result.success
    args, kwargs = client.load_table_from_json.call_args
    row = args[0][0]
    assert row["source_name"] == "fake_source"
    assert row["batch_id"] == result.run_id
    assert row["payload"] is payload
    assert args[1] == "sg-pipeline-dev.dev_raw.fake_source"
    assert kwargs["job_config"].write_disposition == "WRITE_APPEND"


def test_factory_asset_carries_standard_retry_policy():
    asset_def = build_ingestion_asset(_fake_cfg({"value": [1]}))
    policy = asset_def.op.retry_policy
    assert policy is not None
    assert policy.max_retries == 3
    assert policy.delay == 10


def test_factory_asset_name_matches_config():
    asset_def = build_ingestion_asset(_fake_cfg({"value": [1]}))
    names = {k.path[-1] for k in asset_def.keys}
    assert names == {"fake_source"}


from dagster import DefaultScheduleStatus

from orchestrate.defs.ingestion.factory import build_ingestion_schedule


def test_factory_schedule_uses_config_cron_and_sgt():
    sched = build_ingestion_schedule(_fake_cfg({"value": [1]}))
    assert sched.cron_schedule == "*/30 * * * *"
    assert sched.execution_timezone == "Asia/Singapore"
    assert sched.default_status == DefaultScheduleStatus.RUNNING


def test_factory_schedule_names_follow_convention():
    sched = build_ingestion_schedule(_fake_cfg({"value": [1]}))
    assert sched.name == "fake_source_schedule"
    assert sched.job.name == "fake_source_job"


def test_factory_schedule_honours_per_source_cron_override():
    cfg = SourceConfig("hourly_source", _StubExtractor({"value": [1]}), "$.value", cron="0 * * * *")
    sched = build_ingestion_schedule(cfg)
    assert sched.cron_schedule == "0 * * * *"
