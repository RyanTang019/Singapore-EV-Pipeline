"""Registers the dbt models as Dagster assets + an optional schedule that builds them.

`@dbt_assets` stamps one Dagster asset per dbt model out of the manifest; materializing it
runs `dbt build` (models + tests). Wrapped in a `@definitions` function (rather than a bare
module-level asset) so the resource binds in the same Definitions and the asset isn't also
collected loose — load_from_defs_folder discovers and merges this with the ingestion defs.

`dbt_build_schedule` retains the production build's 6-hour cadence for optional reactivation, but
is stopped by default while BigQuery costs are being reduced. The registered `dbt_build_job`
remains available for manual runs. dbt unit tests run in WIF-authenticated CI, so production
excludes that resource type. If re-enabled, the :15 offset keeps the build off ingestion's
:00/:30 boundaries, and dagster.yaml's max_concurrent_runs=1 serializes work on the 4GB VM.
"""

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    DefaultScheduleStatus,
    Definitions,
    ScheduleDefinition,
    define_asset_job,
    definitions,
)
from dagster_dbt import DbtCliResource, dbt_assets

from .project import DBT_TARGET, EvDbtTranslator, ev_dbt_project

DBT_PROD_BUILD_ARGS = ["build", "--exclude-resource-type", "unit_test"]


@definitions
def transform_defs() -> Definitions:
    @dbt_assets(
        manifest=ev_dbt_project.manifest_path,
        dagster_dbt_translator=EvDbtTranslator(),
    )
    def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
        yield from dbt.cli(DBT_PROD_BUILD_ARGS, context=context).stream()

    dbt_build_job = define_asset_job(
        name="dbt_build_job",
        selection=AssetSelection.assets(dbt_models),
    )

    dbt_build_schedule = ScheduleDefinition(
        name="dbt_build_schedule",
        job=dbt_build_job,
        cron_schedule="15 */6 * * *",
        execution_timezone="Asia/Singapore",
        default_status=DefaultScheduleStatus.STOPPED,
    )

    return Definitions(
        assets=[dbt_models],
        jobs=[dbt_build_job],
        schedules=[dbt_build_schedule],
        resources={
            "dbt": DbtCliResource(project_dir=ev_dbt_project, target=DBT_TARGET),
        },
    )
