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

| Dataset          | Purpose                                                     |
| ---------------- | ----------------------------------------------------------- |
| `raw`          | Raw ingested data from APIs (shared — env-neutral)          |
| `prod_staging` | dbt staging models — prod target                            |
| `prod_marts`   | dbt mart models — prod target (Looker Studio reads these)   |
| `dev_staging`  | dbt staging models — dev target (local experimentation)     |
| `dev_marts`    | dbt mart models — dev target                                |

`raw` is shared (dev reads it read-only). dbt's `dev` target is the safe default; production runs use `dbt build --target prod`. IAM bindings grant the Dagster service account `bigquery.dataEditor` on every dataset.

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

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
- [ ] Hetzner firewall: restrict inbound to SSH only
- [ ] Add collaborator (Oliver) SSH key to the VM
- [ ] Workload Identity Federation to remove the long-lived SA key from GitHub Secrets

**Ingestion**

- [ ] Write Python ingestion scripts for LTA EV charging point API
- [ ] Load raw data into BigQuery `raw` dataset via the BigQuery SDK
- [ ] Add additional sources (SingStat population, COE prices, weather)
- [ ] Implement incremental loads

**Transformation**

- [ ] Build dbt staging models to clean and type the raw data
- [ ] Build dbt mart models — fact and dimension tables for analytics
- [ ] Add dbt tests (not null, uniqueness, referential integrity)

**Orchestration**

- [ ] Schedule ingestion jobs via Dagster
- [ ] Implement Dagster Software-Defined Assets
- [ ] Add Dagster sensors for event-driven triggering

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
