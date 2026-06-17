from pathlib import Path

from dagster import load_from_defs_folder

import orchestrate


def _defs():
    root = Path(orchestrate.__file__).parent  # src/orchestrate/
    return load_from_defs_folder(path_within_project=root)


def test_all_three_assets_discovered_by_name():
    names = {k.path[-1] for k in _defs().resolve_asset_graph().get_all_asset_keys()}
    assert {"ev_charger_availability", "traffic_speed_bands", "carpark_availability"} <= names


def test_no_duplicate_asset_keys():
    keys = _defs().resolve_asset_graph().get_all_asset_keys()
    leaf_names = [k.path[-1] for k in keys]
    assert len(leaf_names) == len(set(leaf_names))  # no dupes from old+new both registering


def test_all_three_schedules_discovered_at_30_min():
    defs = _defs()
    for name in ("ev_charger_availability", "traffic_speed_bands", "carpark_availability"):
        sched = defs.resolve_schedule_def(f"{name}_schedule")
        assert sched.cron_schedule == "*/30 * * * *"


def test_ev_schedule_targets_ev_asset():
    defs = _defs()
    sched = defs.resolve_schedule_def("ev_charger_availability_schedule")
    job = defs.resolve_job_def(sched.job.name)
    asset_names = {k.path[-1] for k in job.asset_layer.executable_asset_keys}
    assert "ev_charger_availability" in asset_names
