from pathlib import Path

import orchestrate
from dagster import DefaultScheduleStatus, load_from_defs_folder

from orchestrate.defs.ev_charger_availability.schedule import (
    ev_charger_availability_schedule,
)


def test_schedule_runs_hourly_sgt():
    s = ev_charger_availability_schedule
    assert s.cron_schedule == "0 * * * *"
    assert s.execution_timezone == "Asia/Singapore"
    # RUNNING so the VM daemon activates it on deploy without a manual toggle in Dagit.
    assert s.default_status == DefaultScheduleStatus.RUNNING


def test_schedule_is_discovered_and_targets_the_asset():
    root = Path(orchestrate.__file__).parent  # src/orchestrate/
    defs = load_from_defs_folder(path_within_project=root)

    sched = defs.resolve_schedule_def("ev_charger_availability_schedule")
    assert sched.cron_schedule == "0 * * * *"

    # the scheduled job materializes the ev_charger_availability asset
    job = defs.resolve_job_def(sched.job.name)
    asset_names = {key.path[-1] for key in job.asset_layer.executable_asset_keys}
    assert "ev_charger_availability" in asset_names
