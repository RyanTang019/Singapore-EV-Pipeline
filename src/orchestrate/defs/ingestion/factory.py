"""Asset + schedule factory: stamps one Dagster asset (and its schedule) out of each
SourceConfig. The module-level ingestion_assets / ingestion_schedules lists (added at the
cutover) are what load_from_defs_folder auto-discovers.
"""

import os

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    AssetsDefinition,
    DefaultScheduleStatus,
    MaterializeResult,
    MetadataValue,
    ScheduleDefinition,
    asset,
    define_asset_job,
)

from .landing import load_raw
from .manifest import MANIFEST, STANDARD_RETRY, SourceConfig


def build_ingestion_asset(cfg: SourceConfig) -> AssetsDefinition:
    @asset(
        name=cfg.name,
        group_name="ingestion",
        description=f"LTA {cfg.name} snapshot landed opaquely (whole payload) into raw.",
        retry_policy=STANDARD_RETRY,
    )
    def _asset(context: AssetExecutionContext) -> MaterializeResult:
        batch_id = context.run.run_id
        payload = cfg.extractor.extract(os.environ["LTA_API_KEY"])
        table_id = load_raw(
            cfg.name,
            payload,
            batch_id=batch_id,
            project=os.environ["GCP_PROJECT_ID"],
            dataset=os.environ["BQ_DATASET_RAW"],
        )
        return MaterializeResult(
            metadata={
                "batch_id": MetadataValue.text(batch_id),
                "source_name": MetadataValue.text(cfg.name),
                "table": MetadataValue.text(table_id),
                # display-only freshness/size signal; not persisted as a column
                "payload_records": len(payload.get(cfg.records_key, [])),
            }
        )

    return _asset


def build_ingestion_schedule(cfg: SourceConfig) -> ScheduleDefinition:
    """Per-source schedule. Names follow the existing convention (`<name>_schedule`,
    `<name>_job`) so the EV job/schedule names are unchanged. default_status=RUNNING so the
    VM daemon activates it on deploy without a manual Dagit toggle."""
    job = define_asset_job(
        name=f"{cfg.name}_job",
        selection=AssetSelection.assets(cfg.name),
    )
    return ScheduleDefinition(
        name=f"{cfg.name}_schedule",
        job=job,
        cron_schedule=cfg.cron,
        execution_timezone="Asia/Singapore",
        default_status=DefaultScheduleStatus.RUNNING,
    )


# --- registration: discovered by load_from_defs_folder (atomic cutover, replaces the old
# per-source asset.py/schedule.py modules deleted in the same commit) ---
ingestion_assets = [build_ingestion_asset(c) for c in MANIFEST]
ingestion_schedules = [build_ingestion_schedule(c) for c in MANIFEST]
