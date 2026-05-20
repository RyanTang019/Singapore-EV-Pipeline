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
  orchestrate/    ← Dagster orchestration (dg CLI config)
  transform/      ← dbt transformation (BigQuery adapter)
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

Three datasets provisioned via Terraform in `asia-southeast1`:

| Dataset | Purpose |
|---------|---------|
| `raw` | Raw ingested data from APIs |
| `staging` | dbt staging models — cleaned and typed |
| `marts` | dbt mart models — analytics-ready for Looker Studio |

IAM bindings grant the Dagster service account `bigquery.dataEditor` on all three datasets.

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### VM (Hetzner CPX22)

A Hetzner CPX22 VM ($10.34/mo, 2 vCPU AMD, 4GB RAM, 80GB SSD) hosts Dagster and runs ingestion scripts.

## Next Steps

- [ ] Write Python ingestion scripts for LTA EV charging point API
- [ ] Load raw data into BigQuery `raw` dataset via the BigQuery SDK
- [ ] Build dbt staging models to clean and type the raw data
- [ ] Build dbt mart models for analytics
- [ ] Deploy and configure Dagster on the Hetzner VM
- [ ] Configure service account key on the VM for BigQuery access
- [ ] Schedule ingestion jobs via Dagster

## References

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Dagster](https://docs.dagster.io/) — orchestration
- [dg CLI](https://docs.dagster.io/guides/labs/dg/) — Dagster developer CLI
- [dbt](https://docs.getdbt.com/) — data transformation
- [dbt-bigquery](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup) — BigQuery adapter
- [BigQuery](https://cloud.google.com/bigquery/docs) — data warehouse

