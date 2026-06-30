"""The dbt models are discovered as Dagster assets AND wired downstream of ingestion.

The lineage assertion is the whole point of Path B: the custom translator must map the dbt
`source('raw', 'ev_charger_availability')` onto the ingestion asset key so the graph connects
ingestion -> staging -> mart. Loading the defs folder requires a dbt manifest on disk
(transform/target/manifest.json); `dbt parse`/`dbt build`/`dg dev` all produce it.
"""

from pathlib import Path

import pytest
from dagster import AssetKey, load_from_defs_folder

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


def test_staging_is_downstream_of_ingestion_asset():
    # The translator drops the 'raw' schema segment so the dbt source key equals the
    # ingestion asset key — otherwise staging would dangle off a disconnected external source.
    stg = _graph().get(AssetKey(["staging", "stg_ev_charger_availability"]))
    assert AssetKey(["ev_charger_availability"]) in stg.parent_keys


def test_mart_is_downstream_of_staging():
    fct = _graph().get(AssetKey(["marts", "fct_ev_location_availability"]))
    assert AssetKey(["staging", "stg_ev_charger_availability"]) in fct.parent_keys
