"""Registers the dbt models as Dagster assets + the dbt CLI resource.

`@dbt_assets` stamps one Dagster asset per dbt model out of the manifest; materializing it
runs `dbt build` (models + tests). Wrapped in a `@definitions` function (rather than a bare
module-level asset) so the resource binds in the same Definitions and the asset isn't also
collected loose — load_from_defs_folder discovers and merges this with the ingestion defs.
"""

from dagster import AssetExecutionContext, Definitions, definitions
from dagster_dbt import DbtCliResource, dbt_assets

from .project import DBT_TARGET, EvDbtTranslator, ev_dbt_project


@definitions
def transform_defs() -> Definitions:
    @dbt_assets(
        manifest=ev_dbt_project.manifest_path,
        dagster_dbt_translator=EvDbtTranslator(),
    )
    def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
        yield from dbt.cli(["build"], context=context).stream()

    return Definitions(
        assets=[dbt_models],
        resources={
            "dbt": DbtCliResource(project_dir=ev_dbt_project, target=DBT_TARGET),
        },
    )
