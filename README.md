

# EV Pipeline

Singapore EV data pipeline using Dagster for orchestration and dbt for transformation.

## Setup

Ensure [`uv`](https://docs.astral.sh/uv/) is installed (`brew install uv`), then run:

```bash
./bin/setup
```

This installs Python deps, installs lefthook, wires the pre-push hook, and creates a `.env` from `.env.example` if one doesn't exist. Fill in `LTA_API_KEY` and `DEV_SCHEMA_PREFIX` in `.env`, then authenticate to GCP:

```bash
gcloud auth application-default login
```

The pre-push hook runs `ruff check` and `pytest -x -q` before every push. To bypass in an emergency: `git push --no-verify`.

## Project Structure

```
Singapore-EV-Pipeline/
  src/orchestrate/  ← Dagster orchestration (assets in defs/)
  transform/        ← dbt transformation (BigQuery adapter)
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
./bin/dbt run      # wrapper: applies --profiles-dir/--project-dir transform + .env
```

## Infrastructure

### BigQuery (Terraform)

Datasets are provisioned via Terraform in `asia-southeast1`, split across two GCP projects
(prod `project-f78a2754…`, dev `sg-pipeline-dev`):

| Dataset                  | Purpose                                                              |
| ------------------------ | ------------------------------------------------------------------- |
| `prod_raw`               | Raw ingested data — **production** (the VM writes here)              |
| `dev_raw`                | **Shared** raw ingestion landing zone — all developers write here   |
| `prod_staging`           | dbt staging models — prod target                                    |
| `prod_marts`             | dbt mart models — prod target (Looker Studio reads these)           |
| `dev_<handle>_staging`   | dbt staging models — per-developer dev target (e.g. `dev_ryan_staging`) |
| `dev_<handle>_marts`     | dbt mart models — per-developer dev target                          |

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

## Roadmap

**Infrastructure**

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
- [ ] Workload Identity Federation to remove the long-lived SA key from GitHub Secrets

**Ingestion** — opaque raw landing (ELT)

Every source lands the **whole untouched API response** as one row
`{batch_id, source_name, ingested_at, payload(JSON)}`; all unnesting/exploding happens in dbt
(in-warehouse), never on the VM. Preserving the original payload means a source schema change can
never lose data on this append-only feed. See `docs/superpowers/specs/2026-06-08-opaque-raw-landing-design.md`.

- [X] `ev_charger_availability` asset — `EVCBatch` → 2-step S3 link (5-min expiry, retry-once) →
  envelope guard → one opaque `payload` row → `{BQ_DATASET_RAW}.ev_charger_availability` (`WRITE_APPEND`)
  - [X] Loader creates the table via `CREATE_IF_NEEDED` from a code-owned `RAW_SCHEMA` (no Terraform)
  - [X] Verified live against `dev_raw` (1 row, 2,688 locations queryable via `JSON_QUERY_ARRAY`)
- [ ] TrafficSpeedBands → CarParkAvailability, deliberately per-source on the uniform load
  (`docs/superpowers/specs/2026-06-08-per-source-ingestion-traffic-carpark-design.md`)
- [ ] Config-driven ingestion engine: extract `load_raw` + extractor drivers + asset factory +
  manifest from the 3 concrete sources
- [ ] Dagster schedule (~5–15 min, matching the API refresh)
- [ ] Add remaining sources (transit, demographics, vehicle pop, HDB)

**Transformation**

- [ ] dbt staging model: explode `payload` JSON (`JSON_QUERY_ARRAY(payload, '$.evLocationsData')`) → connector-grain `stg_ev_charger`
- [ ] dbt mart models — fact and dimension tables (star schema on `location_id`)
- [ ] dbt tests (not null, uniqueness, referential integrity)

**Orchestration**

- [ ] Wire dbt as `@dbt_assets` in Dagster (runs `--target prod` on the VM)
- [ ] Schedule the end-to-end pipeline (ingest → dbt)
- [ ] Add sensors / freshness checks as needed

**Observability & Delivery**

- [ ] Add data quality monitoring (Elementary or Great Expectations)
- [ ] Build Looker Studio dashboard on top of marts
- [ ] CI/CD with GitHub Actions (`terraform plan` on PRs, `dbt test` on merge)

## References

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Dagster](https://docs.dagster.io/) — orchestration
- [dg CLI](https://docs.dagster.io/guides/labs/dg/) — Dagster developer CLI
- [dbt](https://docs.getdbt.com/) — data transformation
- [dbt-bigquery](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup) — BigQuery adapter
- [BigQuery](https://cloud.google.com/bigquery/docs) — data warehouse

