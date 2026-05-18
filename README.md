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

## References

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Dagster](https://docs.dagster.io/) — orchestration
- [dg CLI](https://docs.dagster.io/guides/labs/dg/) — Dagster developer CLI
- [dbt](https://docs.getdbt.com/) — data transformation
- [dbt-bigquery](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup) — BigQuery adapter
- [BigQuery](https://cloud.google.com/bigquery/docs) — data warehouse

