# EV Pipeline

Singapore EV data pipeline using Dagster for orchestration and dbt for transformation.

## Setup

Ensure [`uv`](https://docs.astral.sh/uv/) is installed with `brew install uv`, then install all dependencies:

```bash
uv sync
```

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

```bash
uv run dg dev
```

## Running dbt

```bash
uv run dbt run --profiles-dir transform --project-dir transform
```

## Infrastructure

### BigQuery (Terraform)

Datasets provisioned via Terraform in `asia-southeast1`, split by environment (dbt dev/prod targets):

| Dataset              | Purpose                                                       |
| -------------------- | ------------------------------------------------------------- |
| `raw`              | Raw ingested data —**production** (the VM writes here) |
| `dev_raw_<handle>` | Per-developer raw ingestion sandbox (e.g.`dev_raw_ryan`)    |
| `prod_staging`     | dbt staging models — prod target                             |
| `prod_marts`       | dbt mart models — prod target (Looker Studio reads these)    |
| `dev_staging`      | dbt staging models — dev target (shared)                     |
| `dev_marts`        | dbt mart models — dev target (shared)                        |

dbt's `dev` target is the safe default; production runs use `dbt build --target prod`. IAM bindings grant the Dagster service account `bigquery.dataEditor` on every dataset. The per-developer `dev_raw_*` sandboxes are driven by the `developers` Terraform variable (`for_each`), so adding a person is a one-line change.

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Local development — environment selection

Ingestion writes to whatever dataset `BQ_DATASET_RAW` points at, so the dev/prod split is a single env var. **Always point local ingestion at your personal sandbox — never at production `raw`:**

```bash
# Each developer uses their own dev_raw_<handle>:
export BQ_DATASET_RAW=dev_raw_ryan     # (Oliver: dev_raw_oliver)
export LTA_API_KEY=...                  # your own LTA DataMall key
uv run dg dev                           # materialize freely — prod is never touched
```

- **Production** (the VM) sets `BQ_DATASET_RAW=raw` in `docker-compose.yml`; the Dagster schedule runs there. Don't run ingestion locally with `BQ_DATASET_RAW=raw`.
- **dbt:** local `dbt build` defaults to the `dev` target (writes to `dev_staging`/`dev_marts`); production uses `dbt build --target prod`. The `dev_staging`/`dev_marts` datasets are currently **shared** across developers.

### VM (Hetzner CPX22)

A Hetzner CPX22 VM (Falkenstein `fsn1`, static IP) hosts the Dockerised Dagster stack
(postgres, user_code, webserver, daemon). Provisioned by Terraform; cloud-init bootstraps
the host (Docker, gcloud, deploy user, `deploy.sh`). Code is shipped as GHCR images via a
GitHub Actions build + SSH deploy pipeline (no repo clone on the VM).

## Roadmap

**Infrastructure**

- [X] Provision BigQuery datasets via Terraform (`raw` + dev/prod `staging`/`marts`)
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
- [X] Shared landing zone for both develops (dev_raw)
- [X] Verify LTA EV data source against the live API (endpoint, shape, availability)
- [ ] Workload Identity Federation to remove the long-lived SA key from GitHub Secrets

**Ingestion** (Phase 1 = EV charger availability)

> **Next up — Phase 1: first ingestion asset.** Build EV charger availability end-to-end
> (LTA `EVCBatch` → `raw.ev_charger_availability`), then a schedule, then the first dbt
> staging model. Once one asset works, the other sources follow the same pattern.

- [ ] BigQuery resource + `ev_charger_availability` asset in `src/orchestrate/defs/`
  - [ ] 2-step fetch: `EVCBatch` → temporary S3 link → download snapshot (handle 5-min expiry)
  - [ ] Land **grain B**: one row per location, `chargingPoints` as JSON + `ingested_at` + `last_updated_time`
  - [ ] Write to `{BQ_DATASET_RAW}.ev_charger_availability` (`WRITE_APPEND`)
- [ ] Test locally against `dev_raw_<handle>`, then deploy and materialize in prod
- [ ] Dagster schedule (~5–15 min, matching the API refresh)
- [ ] Add remaining sources (traffic, carpark, transit, demographics, vehicle pop, HDB)

**Transformation**

- [ ] dbt staging model: unnest `raw` JSON → connector-grain `stg_ev_charger`
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

#
