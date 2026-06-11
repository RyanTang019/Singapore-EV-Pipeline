"""Schedule for the EV charger availability ingestion asset.

Hourly cadence (Asia/Singapore). NOTE: EVCBatch refreshes ~every 5 min and each snapshot
is unrecoverable (5-min S3 expiry, no history endpoint), so hourly still drops ~11 of
every 12 snapshots. Hourly is a deliberate first prod cadence (manageable row volume, real
intra-day trend); tighten toward ~5-15 min before relying on fine-grained peak-hour /
utilisation analytics.

Auto-discovered by `load_from_defs_folder`. `default_status=RUNNING` so the VM daemon
activates it on deploy without a manual toggle in Dagit.
"""

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    ScheduleDefinition,
    define_asset_job,
)

ev_charger_availability_job = define_asset_job(
    name="ev_charger_availability_job",
    selection=AssetSelection.assets("ev_charger_availability"),
)

ev_charger_availability_schedule = ScheduleDefinition(
    name="ev_charger_availability_schedule",
    job=ev_charger_availability_job,
    cron_schedule="0 * * * *",  # top of every hour, SGT (24×/day)
    execution_timezone="Asia/Singapore",
    default_status=DefaultScheduleStatus.RUNNING,
)
