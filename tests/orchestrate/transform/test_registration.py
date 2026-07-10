"""The dbt models are discovered as Dagster assets AND wired downstream of ingestion.

The lineage assertion is the whole point of Path B: the custom translator must map the dbt
`source('raw', 'ev_charger_availability')` onto the ingestion asset key so the graph connects
ingestion -> staging -> mart. Loading the defs folder requires a dbt manifest on disk
(transform/target/manifest.json); `dbt parse`/`dbt build`/`dg dev` all produce it.
"""

from pathlib import Path

import pytest
from dagster import AssetKey, DefaultScheduleStatus, load_from_defs_folder

import orchestrate

_ROOT = Path(orchestrate.__file__).resolve().parents[2]
MANIFEST = _ROOT / "transform" / "target" / "manifest.json"

pytestmark = pytest.mark.skipif(
    not MANIFEST.exists(),
    reason="dbt manifest not built (run `./bin/dbt parse`); CI builds it before pytest",
)


def _graph():
    root = Path(orchestrate.__file__).parent
    return load_from_defs_folder(path_within_project=root).resolve_asset_graph()


def test_dbt_models_discovered_as_assets():
    keys = {"/".join(k.path) for k in _graph().get_all_asset_keys()}
    assert "staging/stg_ev_charger_availability" in keys
    assert "marts/fct_ev_location_availability" in keys
    # spatial foundation + per-source facts (2026-07-10 mart build)
    for k in [
        "seed/planning_areas",
        "marts/dim_planning_area",
        "intermediate/int_ev_tagged",
        "intermediate/int_carpark_tagged",
        "intermediate/int_traffic_links",
        "marts/fct_carpark_availability",
        "marts/fct_traffic_congestion",
    ]:
        assert k in keys, k


def test_staging_is_downstream_of_ingestion_asset():
    # The translator drops the 'raw' schema segment so the dbt source key equals the
    # ingestion asset key — otherwise staging would dangle off a disconnected external source.
    stg = _graph().get(AssetKey(["staging", "stg_ev_charger_availability"]))
    assert AssetKey(["ev_charger_availability"]) in stg.parent_keys


def test_mart_is_downstream_of_staging():
    # EV fact now sources from int_ev_tagged (planning_area + time features), which
    # in turn descends from staging. Assert the new direct parent and the chain.
    fct = _graph().get(AssetKey(["marts", "fct_ev_location_availability"]))
    assert AssetKey(["intermediate", "int_ev_tagged"]) in fct.parent_keys
    ev_int = _graph().get(AssetKey(["intermediate", "int_ev_tagged"]))
    assert AssetKey(["staging", "stg_ev_charger_availability"]) in ev_int.parent_keys


def test_carpark_and_traffic_facts_downstream_of_ingestion():
    cp = _graph().get(AssetKey(["marts", "fct_carpark_availability"]))
    assert AssetKey(["intermediate", "int_carpark_tagged"]) in cp.parent_keys
    cp_int = _graph().get(AssetKey(["intermediate", "int_carpark_tagged"]))
    assert AssetKey(["staging", "stg_carpark_availability"]) in cp_int.parent_keys

    links = _graph().get(AssetKey(["intermediate", "int_traffic_links"]))
    assert AssetKey(["staging", "stg_traffic_speed_bands"]) in links.parent_keys
    tc = _graph().get(AssetKey(["marts", "fct_traffic_congestion"]))
    assert AssetKey(["intermediate", "int_traffic_links"]) in tc.parent_keys


def test_dbt_build_schedule_registered():
    defs = load_from_defs_folder(path_within_project=Path(orchestrate.__file__).parent)
    sched = defs.resolve_schedule_def("dbt_build_schedule")
    assert sched.cron_schedule == "15 */6 * * *"
    assert sched.execution_timezone == "Asia/Singapore"
    assert sched.default_status == DefaultScheduleStatus.RUNNING


def test_dbt_build_job_selects_the_dbt_models():
    defs = load_from_defs_folder(path_within_project=Path(orchestrate.__file__).parent)
    sched = defs.resolve_schedule_def("dbt_build_schedule")
    job = defs.resolve_job_def(sched.job.name)
    selected = {"/".join(k.path) for k in job.asset_layer.executable_asset_keys}
    assert "staging/stg_ev_charger_availability" in selected
    assert "marts/fct_ev_location_availability" in selected
