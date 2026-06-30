"""dbt project handle for the Dagster ingestion->transform DAG.

`DbtProject` points dagster-dbt at transform/ (profiles.yml lives there too). The custom
translator maps dbt's raw *sources* onto the ingestion asset keys so the asset graph connects
end to end: ingestion asset -> dbt staging -> dbt mart.
"""

import os
from pathlib import Path

from dagster import AssetKey
from dagster_dbt import DagsterDbtTranslator, DbtProject

# This file: src/orchestrate/defs/transform/project.py -> repo root is parents[4].
TRANSFORM_DIR = Path(__file__).resolve().parents[4] / "transform"

ev_dbt_project = DbtProject(project_dir=TRANSFORM_DIR)
# Regenerates target/manifest.json on `dg dev` (no effect outside dev). Outside dev (tests,
# prod container) a manifest must already exist on disk — baked into the image, see Commit 2.
ev_dbt_project.prepare_if_dev()


class EvDbtTranslator(DagsterDbtTranslator):
    """Drop the schema segment from dbt *source* asset keys so they equal the ingestion keys.

    dagster-dbt defaults a source to ``['<schema>', '<table>']`` -> e.g.
    ``['raw', 'ev_charger_availability']``, but the Dagster ingestion asset is keyed
    ``['ev_charger_availability']`` (factory.py
    ``name=cfg.name``). Matching them lets Dagster see ``stg_ev_charger_availability`` as
    downstream of the ingestion asset instead of a disconnected external source. Models keep
    their default ``['staging'|'marts', <name>]`` keys.
    """

    def get_asset_key(self, dbt_resource_props: dict) -> AssetKey:
        if dbt_resource_props["resource_type"] == "source":
            return AssetKey([dbt_resource_props["identifier"]])
        return super().get_asset_key(dbt_resource_props)


# dbt's "prod must be opted into" rule (profiles.yml defaults to dev) carried over to the
# orchestrated path: dev is the safe default; the VM sets DBT_TARGET=prod in its .env.
DBT_TARGET = os.getenv("DBT_TARGET", "dev")
