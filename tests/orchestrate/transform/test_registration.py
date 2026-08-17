"""The dbt models are discovered as Dagster assets AND wired downstream of ingestion.

The lineage assertion is the whole point of Path B: the custom translator must map the dbt
`source('raw', 'ev_charger_availability')` onto the ingestion asset key so the graph connects
ingestion -> staging -> mart. Loading the defs folder requires a dbt manifest on disk
(transform/target/manifest.json); `dbt parse`/`dbt build`/`dg dev` all produce it.
"""

from pathlib import Path

import pytest
from dagster import AssetKey, DefaultScheduleStatus, load_from_defs_folder

import orchestrate
from orchestrate.defs.transform.definitions import DBT_PROD_BUILD_ARGS

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
    # spatial foundation + per-source facts (2026-07-10 mart build)
    for k in [
        "seed/planning_areas",
        "marts/dim_planning_area",
        "intermediate/int_ev_tagged",
        "intermediate/int_carpark_tagged",
        "intermediate/int_traffic_links",
        "marts/fct_carpark_availability",
        "marts/fct_traffic_congestion",
        "marts/rpt_ev_availability_current",
        "marts/rpt_carpark_availability_current",
        "marts/rpt_traffic_congestion_current",
        "seed/planning_area_population",
        "seed/planning_area_population_releases",
        "marts/stg_planning_area_population",
        "marts/stg_planning_area_population_releases",
        "marts/fct_planning_area_population",
        "marts/fct_supply_demand_daily",
        "marts/mart_supply_demand_gap",
        "marts/rpt_supply_demand_gap_current",
        "seed/lta_monthly_vehicle_population_by_fuel",
        "seed/lta_monthly_vehicle_population_releases",
        "seed/lta_fuel_type_classification",
        "staging/stg_lta_monthly_vehicle_population_by_fuel",
        "staging/stg_lta_monthly_vehicle_population_releases",
        "marts/fct_national_ev_adoption_monthly",
        "marts/mart_national_ev_adoption_monthly",
        "marts/rpt_national_ev_adoption_current",
    ]:
        assert k in keys, k


def test_staging_is_downstream_of_ingestion_asset():
    # The translator drops the 'raw' schema segment so the dbt source key equals the
    # ingestion asset key — otherwise staging would dangle off a disconnected external source.
    stg = _graph().get(AssetKey(["staging", "stg_ev_charger_availability"]))
    assert AssetKey(["ev_charger_availability"]) in stg.parent_keys


def test_mart_is_downstream_of_staging():
    # EV fact now sources from int_ev_tagged (planning_area + time features), which
    # in turn descends from staging. Assert the new direct parent and the chain.
    fct = _graph().get(AssetKey(["marts", "fct_ev_location_availability"]))
    assert AssetKey(["intermediate", "int_ev_tagged"]) in fct.parent_keys
    ev_int = _graph().get(AssetKey(["intermediate", "int_ev_tagged"]))
    assert AssetKey(["staging", "stg_ev_charger_availability"]) in ev_int.parent_keys


def test_carpark_and_traffic_facts_downstream_of_ingestion():
    cp = _graph().get(AssetKey(["marts", "fct_carpark_availability"]))
    assert AssetKey(["intermediate", "int_carpark_tagged"]) in cp.parent_keys
    cp_int = _graph().get(AssetKey(["intermediate", "int_carpark_tagged"]))
    assert AssetKey(["staging", "stg_carpark_availability"]) in cp_int.parent_keys

    links = _graph().get(AssetKey(["intermediate", "int_traffic_links"]))
    assert AssetKey(["staging", "stg_traffic_speed_bands"]) in links.parent_keys
    tc = _graph().get(AssetKey(["marts", "fct_traffic_congestion"]))
    assert AssetKey(["intermediate", "int_traffic_links"]) in tc.parent_keys


def test_current_reporting_assets_follow_their_facts():
    ev = _graph().get(AssetKey(["marts", "rpt_ev_availability_current"]))
    assert AssetKey(["marts", "fct_ev_location_availability"]) in ev.parent_keys

    cp = _graph().get(AssetKey(["marts", "rpt_carpark_availability_current"]))
    assert AssetKey(["marts", "fct_carpark_availability"]) in cp.parent_keys

    traffic = _graph().get(AssetKey(["marts", "rpt_traffic_congestion_current"]))
    assert AssetKey(["marts", "fct_traffic_congestion"]) in traffic.parent_keys
    assert AssetKey(["marts", "dim_planning_area"]) in traffic.parent_keys


def test_population_and_supply_demand_lineage():
    graph = _graph()

    population_staging = graph.get(
        AssetKey(["marts", "stg_planning_area_population"])
    )
    assert AssetKey(["seed", "planning_area_population"]) in population_staging.parent_keys

    release_staging = graph.get(
        AssetKey(["marts", "stg_planning_area_population_releases"])
    )
    assert (
        AssetKey(["seed", "planning_area_population_releases"])
        in release_staging.parent_keys
    )

    population_fact = graph.get(
        AssetKey(["marts", "fct_planning_area_population"])
    )
    assert AssetKey(["marts", "stg_planning_area_population"]) in population_fact.parent_keys
    assert (
        AssetKey(["marts", "stg_planning_area_population_releases"])
        in population_fact.parent_keys
    )
    assert AssetKey(["marts", "dim_planning_area"]) in population_fact.parent_keys

    daily_fact = graph.get(AssetKey(["marts", "fct_supply_demand_daily"]))
    assert AssetKey(["marts", "fct_ev_location_availability"]) in daily_fact.parent_keys
    assert AssetKey(["marts", "dim_planning_area"]) in daily_fact.parent_keys
    assert AssetKey(["marts", "fct_planning_area_population"]) in daily_fact.parent_keys

    gap_mart = graph.get(AssetKey(["marts", "mart_supply_demand_gap"]))
    assert AssetKey(["marts", "fct_supply_demand_daily"]) in gap_mart.parent_keys

    current_report = graph.get(
        AssetKey(["marts", "rpt_supply_demand_gap_current"])
    )
    assert AssetKey(["marts", "mart_supply_demand_gap"]) in current_report.parent_keys


def test_national_ev_adoption_lineage():
    graph = _graph()

    fuel_staging = graph.get(
        AssetKey(["staging", "stg_lta_monthly_vehicle_population_by_fuel"])
    )
    assert (
        AssetKey(["seed", "lta_monthly_vehicle_population_by_fuel"])
        in fuel_staging.parent_keys
    )

    release_staging = graph.get(
        AssetKey(["staging", "stg_lta_monthly_vehicle_population_releases"])
    )
    assert (
        AssetKey(["seed", "lta_monthly_vehicle_population_releases"])
        in release_staging.parent_keys
    )

    fact = graph.get(AssetKey(["marts", "fct_national_ev_adoption_monthly"]))
    assert (
        AssetKey(["staging", "stg_lta_monthly_vehicle_population_by_fuel"])
        in fact.parent_keys
    )
    assert (
        AssetKey(["staging", "stg_lta_monthly_vehicle_population_releases"])
        in fact.parent_keys
    )
    assert AssetKey(["seed", "lta_fuel_type_classification"]) in fact.parent_keys

    mart = graph.get(AssetKey(["marts", "mart_national_ev_adoption_monthly"]))
    assert AssetKey(["marts", "fct_national_ev_adoption_monthly"]) in mart.parent_keys

    report = graph.get(AssetKey(["marts", "rpt_national_ev_adoption_current"]))
    assert AssetKey(["marts", "mart_national_ev_adoption_monthly"]) in report.parent_keys

    # The adoption chain must stay fully independent of the supply-demand chain:
    # no edge in either direction.
    adoption_keys = {
        AssetKey(["seed", "lta_monthly_vehicle_population_by_fuel"]),
        AssetKey(["seed", "lta_monthly_vehicle_population_releases"]),
        AssetKey(["seed", "lta_fuel_type_classification"]),
        AssetKey(["staging", "stg_lta_monthly_vehicle_population_by_fuel"]),
        AssetKey(["staging", "stg_lta_monthly_vehicle_population_releases"]),
        AssetKey(["marts", "fct_national_ev_adoption_monthly"]),
        AssetKey(["marts", "mart_national_ev_adoption_monthly"]),
        AssetKey(["marts", "rpt_national_ev_adoption_current"]),
    }
    supply_demand_keys = {
        AssetKey(["marts", "fct_supply_demand_daily"]),
        AssetKey(["marts", "mart_supply_demand_gap"]),
        AssetKey(["marts", "rpt_supply_demand_gap_current"]),
    }
    for key in supply_demand_keys:
        assert not adoption_keys & graph.get(key).parent_keys, key
    for key in adoption_keys:
        assert not supply_demand_keys & graph.get(key).parent_keys, key


def test_dbt_build_schedule_registered_but_stopped_by_default():
    defs = load_from_defs_folder(path_within_project=Path(orchestrate.__file__).parent)
    sched = defs.resolve_schedule_def("dbt_build_schedule")
    assert sched.cron_schedule == "15 */6 * * *"
    assert sched.execution_timezone == "Asia/Singapore"
    assert sched.default_status == DefaultScheduleStatus.STOPPED


def test_dbt_build_job_selects_the_dbt_models():
    defs = load_from_defs_folder(path_within_project=Path(orchestrate.__file__).parent)
    sched = defs.resolve_schedule_def("dbt_build_schedule")
    job = defs.resolve_job_def(sched.job.name)
    selected = {"/".join(k.path) for k in job.asset_layer.executable_asset_keys}
    assert "staging/stg_ev_charger_availability" in selected
    assert "marts/fct_ev_location_availability" in selected


def test_prod_dbt_build_excludes_unit_tests_owned_by_ci():
    assert DBT_PROD_BUILD_ARGS == ["build", "--exclude-resource-type", "unit_test"]
