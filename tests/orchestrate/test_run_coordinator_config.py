"""dagster.yaml must pin the run coordinator to serial execution.

QueuedRunCoordinator defaults max_concurrent_runs to 10 when unset; the 4GB VM
is intended to run one job at a time (PROJECT_CONTEXT). Three ingestion schedules
already fire together every :00/:30, and manual work can overlap them — so serial execution
must be pinned to 1 explicitly.
"""

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]  # repo root: tests/orchestrate/ -> ../../


def test_run_coordinator_is_serial():
    cfg = yaml.safe_load((_ROOT / "dagster.yaml").read_text())
    coordinator = cfg["run_coordinator"]
    assert coordinator["class"] == "QueuedRunCoordinator"
    assert coordinator["config"]["max_concurrent_runs"] == 1
