# EV Pipeline

Singapore EV data pipeline using Dagster for orchestration and dbt for transformation.

## The Problem

> **Where and when is Singapore's EV charging supply mismatched to demand — and is
> infrastructure being built where it's actually needed?**

This is the domain question the whole pipeline exists to answer. Everything below — ingestion,
the warehouse, dbt models, orchestration, the dashboard — is plumbing in service of it.

Charger availability is captured **every 30 minutes and appended** (never overwritten), so the
warehouse accrues a historical time series rather than a snapshot. That time series is the core
asset: it lets us ask **when** (peak-hour / day-of-week saturation), while planning-area population
and charger density let us ask **where** supply is structurally under- or over-provisioned. A
separate national adoption chain tracks how quickly Singapore's registered vehicle fleet is
electrifying; it is context, not observed planning-area EV ownership.

The aim is to move from *descriptive* ("here is current charger utilisation") to a *supply–demand
mismatch* read — identifying under-served areas and the times infrastructure is most strained.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) — Python package manager (`brew install uv`). Manages the Python 3.10+ toolchain for you.
- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install) — for BigQuery authentication (`brew install --cask google-cloud-sdk`).
- **GCP access** — your Google account needs IAM access to the dev project (`sg-pipeline-dev`) and its `dev_raw` dataset. Ask a project admin to grant it *before* you start; otherwise auth succeeds but every query 403s.
- An [LTA DataMall](https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html) API key (free, self-serve) for ingestion.

> **Public-repository note:** the hosted GCP and Hetzner environments are not shared with readers.
> Running a fork end to end requires your own cloud projects, credentials, and LTA DataMall key;
> the screenshots and eventual view-only dashboard are the zero-setup portfolio demo.

## Setup

From the repo root:

```bash
./bin/setup
```

This installs Python deps, installs lefthook, wires the pre-push hook, and creates a `.env` from `.env.example` if one doesn't exist. Then:

1. Fill in `.env` — at minimum `LTA_API_KEY` and `DEV_SCHEMA_PREFIX` (`dev_<your_handle>`). Confirm the GCP defaults: `GCP_PROJECT_ID=sg-pipeline-dev`, `GCP_REGION=asia-southeast1`, and **leave `BQ_DATASET_RAW=dev_raw`** (the shared dev landing zone — never `prod_raw`).
2. Authenticate to BigQuery via Application Default Credentials:

   ```bash
   gcloud auth application-default login
   ```

The pre-push hook runs `ruff check` and `pytest -x -q` before every push. To bypass in an emergency: `git push --no-verify`.

## Quickstart — first end-to-end run

The pipeline runs in two stages: **ingest** (Dagster writes raw API payloads to `dev_raw`) → **transform** (dbt reads `dev_raw` and builds your `dev_<handle>_staging` / `_marts`).

1. **Start Dagster locally** (see [Running Dagster](#running-dagster) for why the wrapper):

   ```bash
   ./bin/dg-dev
   ```

2. **Materialize the ingestion assets** to populate `dev_raw`. In the Dagster UI (http://localhost:3000), materialize the three source assets — `ev_charger_availability`, `traffic_speed_bands`, `carpark_availability`.

3. **Build the dbt models** (reads `dev_raw`, writes your dev schemas):

   ```bash
   ./bin/dbt build
   ```

   Use `build`, not `run` — `build` also loads the seeds used by the spatial and national-adoption
   models, then runs models and tests in DAG order.

## Project Structure

```
Singapore-EV-Pipeline/
  src/orchestrate/  ← Dagster orchestration (assets in defs/)
  scripts/          ← deterministic controlled-source seed generators
  transform/        ← dbt staging, intermediate, mart, report, and seed layers
  terraform/        ← infrastructure as code (BigQuery, IAM, Secret Manager, Hetzner VM)
```

### How this was initialised

```bash
uv init
uvx create-dagster orchestrate
uvx --with dbt-bigquery dbt init transform --skip-profile-setup
```

## Running Dagster

Use the local wrapper (a SQLite Dagster instance that bypasses the VM-only `dagster.yaml`):

```bash
./bin/dg-dev
```

> Don't run bare `uv run dg dev` locally — it loads the VM-only `dagster.yaml` (Postgres +
> DockerRunLauncher) and crashes on missing `DAGSTER_POSTGRES_*` vars.

## Running dbt

```bash
./bin/dbt build    # wrapper: applies --profiles-dir/--project-dir transform + .env
```

`build` loads seeds, runs models, and runs tests in DAG order — prefer it over bare `run`,
which skips the `planning_areas` seed the spatial models depend on. Defaults to the `dev`
target; production uses `./bin/dbt build --target prod`.

## National EV adoption context

The implemented national-adoption feature uses LTA DataMall's **Monthly Motor Vehicle Population
Statistics by Type of Fuel Used (M09)**. The current controlled release covers January 2016 through
May 2026 at national `month_end × vehicle type × source fuel type` grain.

```text
official LTA M09 ZIP (local, gitignored)
  → deterministic observation + release-metadata seeds
  → staging views
  → fct_national_ev_adoption_monthly
  → mart_national_ev_adoption_monthly
  → rpt_national_ev_adoption_current
  → Looker Studio page (pending)
```

The mart exposes registered stock, shares, and month-over-month/year-over-year change for five
vehicle types plus an `all_vehicles` rollup. Its versioned policy treats `Electric` as BEV and only
the two source labels containing `(Plug-In)` as PHEV; conventional petrol-electric and
diesel-electric hybrids are not plug-in vehicles. The current report fails closed unless the latest
month has all six complete scopes, and exposes date references as strings so a Looker date control
cannot hide the page.

This dataset is **national only**. It must not be allocated across planning areas or injected into
the within-date residential supply-demand rank as if it measured local EV ownership. Refreshes are
controlled source updates, not scheduled API ingestion: retrieve and review the official archive,
then regenerate the committed seed pair with
[`scripts/generate_lta_vehicle_population_seed.py`](scripts/generate_lta_vehicle_population_seed.py).
The tracked [seed schema and tests](transform/seeds/national_ev_adoption.yml) document the public
data contract.

## Infrastructure

### BigQuery (Terraform)

Datasets are provisioned via Terraform in `asia-southeast1`, split across two GCP projects
(prod `project-f78a2754…`, dev `sg-pipeline-dev`):

| Dataset                  | Purpose                                                                   |
| ------------------------ | ------------------------------------------------------------------------- |
| `prod_raw`             | Raw ingested data —**production** (the VM writes here)             |
| `dev_raw`              | **Shared** raw ingestion landing zone — all developers write here  |
| `prod_staging`         | dbt staging models — prod target                                         |
| `prod_marts`           | dbt mart models — prod target (Looker Studio reads these)                |
| `dev_<handle>_staging` | dbt staging models — per-developer dev target (e.g.`dev_ryan_staging`) |
| `dev_<handle>_marts`   | dbt mart models — per-developer dev target                               |

dbt's `dev` target is the safe default; production runs use `./bin/dbt build --target prod`. IAM
grants the Dagster service account `bigquery.dataEditor` on every dataset.

> **Raw tables are code-owned, not Terraform-managed.** Terraform provisions the *datasets* and
> IAM; the ingestion loader creates each raw *table* on first run (`CREATE_IF_NEEDED` against a
> Python schema). This keeps raw resilient to source schema changes — see "Ingestion" below.

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Local development — environment selection

Ingestion writes to whatever dataset `BQ_DATASET_RAW` points at, so the dev/prod split is a single
env var. **Always point local ingestion at the shared dev landing zone — never at production
`prod_raw`:**

```bash
# .env (local dev) — authenticate to BigQuery via ADC, not a key file:
GCP_PROJECT_ID=sg-pipeline-dev
GCP_REGION=asia-southeast1      # dbt profiles.yml reads this for the BigQuery location
BQ_DATASET_RAW=dev_raw          # shared landing zone (all devs write here)
DEV_SCHEMA_PREFIX=dev_<handle>  # your private staging/marts (dbt appends _staging/_marts)
LTA_API_KEY=...                 # your own LTA DataMall key
# then: gcloud auth application-default login   (ADC; do NOT set GOOGLE_APPLICATION_CREDENTIALS)
./bin/dg-dev                    # materialize freely — prod is never touched
```

- **Production** (the VM) sets `GCP_PROJECT_ID` to the prod project + `BQ_DATASET_RAW=prod_raw` from
  Secret Manager; the Dagster schedule runs there. Don't run ingestion locally against `prod_raw`.
- **dbt:** local `./bin/dbt build` defaults to the `dev` target (writes to your
  `dev_<handle>_staging`/`_marts`); production uses `./bin/dbt build --target prod`.

### VM (Hetzner CPX22)

A Hetzner CPX22 VM (Falkenstein `fsn1`, static IP) hosts the Dockerised Dagster stack
(postgres, user_code, webserver, daemon). Provisioned by Terraform; cloud-init bootstraps
the host (Docker, gcloud, deploy user, `deploy.sh`). Code is shipped as GHCR images via a
GitHub Actions build + SSH deploy pipeline (no repo clone on the VM).

## Project status

The engineering path is implemented end to end.

**Infrastructure and delivery**

- [X] Provision BigQuery datasets via Terraform (`prod_raw` + shared `dev_raw` + dev/prod `staging`/`marts`)
- [X] IAM bindings for Dagster service account
- [X] dbt dev/prod targets in `profiles.yml` (oauth dev, service-account prod)
- [X] Rent Hetzner CPX22 VM for hosting Dagster
- [X] Terraform the Hetzner VM provisioning + static IP
- [X] cloud-init bootstrap (Docker, gcloud, deploy user, `deploy.sh`)
- [X] Service account key + runtime secrets via GitHub Secrets / GCP Secret Manager
- [X] GitHub Actions: build + push SHA-tagged images to GHCR
- [X] CI/CD SSH deploy pipeline (replaces Watchtower; pinned versions, rollback, audit trail)
- [X] Dockerised Dagster stack running end-to-end on the VM (code location loads green)
- [X] Hetzner firewall: restrict inbound to SSH only
- [X] Shared landing zone for both developers (`dev_raw`)
- [X] Verify LTA EV data source against the live API (endpoint, shape, availability)
- [X] Scoped Workload Identity Federation for CI and Terraform GitHub Actions jobs

**Ingestion** — opaque raw landing (ELT)

Every source lands the **whole untouched API response** as one row
`{batch_id, source_name, ingested_at, payload(JSON)}`; all unnesting/exploding happens in dbt
(in-warehouse), never on the VM. Preserving the original payload means a source schema change can
never lose data on this append-only feed. The tracked
[`landing.py`](src/orchestrate/defs/ingestion/landing.py) module is the shared write boundary.

- [X] `ev_charger_availability` asset — `EVCBatch` → 2-step S3 link (5-min expiry, retry-once) →
  envelope guard → one opaque `payload` row → `{BQ_DATASET_RAW}.ev_charger_availability` (`WRITE_APPEND`)
  - [X] Loader creates the table via `CREATE_IF_NEEDED` from a code-owned `RAW_SCHEMA` (no Terraform)
  - [X] Verified live against `dev_raw` (1 row, 2,688 locations queryable via `JSON_QUERY_ARRAY`)
- [X] Controlled LTA M09 national vehicle-population seed workflow (separate from scheduled raw
  ingestion)
- [X] `TrafficSpeedBands` and `CarParkAvailabilityv2` on the same opaque landing boundary
- [X] Config-driven ingestion engine: extract `load_raw` + extractor drivers + asset factory +
  manifest from the 3 concrete sources
- [X] Independent 30-minute Dagster schedules for all three live sources
- [ ] Add remaining scheduled sources (transit, HDB, and other demand proxies)

**Transformation**

- [X] National EV adoption chain: controlled seeds → staging → fuel-grain fact → monthly
  six-scope mart → fail-closed current report
- [X] National-adoption schema, singular, unit, anchor, reconciliation, lineage, and isolated CI
  build coverage
- [X] dbt staging models explode and type all three opaque source payloads
- [X] Spatial intermediate models tag EV locations, carparks, and traffic links to planning areas
- [X] Charger, carpark, traffic, population, supply-demand, and national-adoption marts and reports
- [X] Schema, singular, unit, anchor, lineage, grain, reconciliation, and fail-closed report tests

**Orchestration**

- [X] Register dbt models as Dagster `@dbt_assets` using the production target on the VM
- [X] Run the three ingestion schedules independently every 30 minutes
- [ ] Reactivate the registered six-hour dbt build schedule after the dashboard refresh review
- [ ] Add sensors / freshness checks as needed

**Observability & Delivery**

- [ ] Add data quality monitoring (Elementary or Great Expectations)
- [ ] Build the Looker Studio national EV adoption page on
  `rpt_national_ev_adoption_current` and `mart_national_ev_adoption_monthly`
- [ ] Finish the remaining Looker Studio dashboard pages on top of marts
- [X] Credential-free pull-request CI plus WIF-backed BigQuery tests and Terraform delivery on
  trusted pushes to `main`
- [ ] Configure required approval on the GitHub `production` environment when the repository is
  made public
- [ ] Replace the Hetzner runtime's long-lived GCP service-account key with an external workload
  identity mechanism
- [ ] Add dashboard screenshots and an optional view-only link from the tracked `assets/` directory

## License and data attribution

The project's original code and documentation are available under the [MIT License](LICENSE).
Government-source datasets retain their own terms; see [Data sources and
attribution](DATA_SOURCES.md) for the applicable Singapore Open Data Licence notices, source links,
and retrieval dates. This independent portfolio project is not endorsed by its data providers.

## References

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Dagster](https://docs.dagster.io/) — orchestration
- [dg CLI](https://docs.dagster.io/guides/labs/dg/) — Dagster developer CLI
- [dbt](https://docs.getdbt.com/) — data transformation
- [dbt-bigquery](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup) — BigQuery adapter
- [BigQuery](https://cloud.google.com/bigquery/docs) — data warehouse
