"""Registers the dbt models as Dagster assets + a schedule that builds them.

`@dbt_assets` stamps one Dagster asset per dbt model out of the manifest; materializing it
runs `dbt build` (models + tests). Wrapped in a `@definitions` function (rather than a bare
module-level asset) so the resource binds in the same Definitions and the asset isn't also
collected loose — load_from_defs_folder discovers and merges this with the ingestion defs.

`dbt_build_schedule` runs the production build every 6 hours (SGT), at :15 past the hour. dbt unit
tests run in WIF-authenticated CI, so production excludes that resource type. The :15
offset keeps it off ingestion's :00/:30 boundaries, so it fires alone — after the :00 ingestion
tick has finished — rather than being enqueued at the same instant. dagster.yaml's
max_concurrent_runs=1 still serializes everything on the 4GB VM as a backstop.
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
        default_status=DefaultScheduleStatus.RUNNING,
    )

    return Definitions(
        assets=[dbt_models],
        jobs=[dbt_build_job],
        schedules=[dbt_build_schedule],
        resources={
            "dbt": DbtCliResource(project_dir=ev_dbt_project, target=DBT_TARGET),
        },
    )
