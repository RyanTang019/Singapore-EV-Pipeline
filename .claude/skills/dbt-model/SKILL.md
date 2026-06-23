---
name: dbt-model
description: >
  Use when creating, modifying, or reviewing dbt models in the Singapore-EV-Pipeline.
  Triggers: "create model", "write model", "add model", "new model", "dbt model",
  "staging model", "mart model", or any dbt SQL/YML authoring task in the transform directory.
---

# dbt Model Authoring

**Creating** -> Layer Rules below | **Reviewing** -> Common Mistakes at bottom | **Testing** -> Testing section

## Layer Quick Reference

| Layer | Schema | Materialization | Naming | Key Rules |
|-------|--------|-----------------|--------|-----------|
| **Staging** | `staging` | `view` (always) | `stg_[source]__[table]` (double underscore) | Only layer using `source()`. Explodes raw JSON payloads. No business logic beyond unnesting |
| **Marts** | `marts` | `table` or `incremental` | Dim: `dim_[entity]`, Fact: `fct_[grain]_[noun]s` | Business-serving. References staging models only — never source() directly |

Schemas are configured in `dbt_project.yml` (`+schema: staging` / `+schema: marts`). Dev target appends `DEV_SCHEMA_PREFIX` (e.g. `dev_ryan_staging`); prod target uses bare schema names.

## Model Structure

**Import CTEs at the top** — all `ref()`/`source()` calls must be standalone CTEs before any transformation.

```sql
{{ config(materialized="view") }}

with source as (
    select * from {{ source('raw', 'ev_charger_availability') }}
),

exploded as (
    select
        batch_id,
        ingested_at,
        json_value(location, '$.name')                         as name,
        json_value(location, '$.address')                      as address,
        json_value(location, '$.postalCode')                   as postal_code,
        cast(json_value(location, '$.latitude') as float64)    as latitude,
        cast(json_value(location, '$.longtitude') as float64)  as longitude,
        json_query(location, '$.chargingPoints')               as charging_points,
        json_value(payload, '$.LastUpdatedTime')               as last_updated_time
    from source,
    unnest(json_query_array(payload, '$.evLocationsData')) as location
),

final as (
    select * from exploded
)

select * from final
```

**Rules:**
- Import CTEs = pure `SELECT * FROM ref()/source()`. No filters, no joins, no transformations
- Logic goes in separate named CTEs after imports
- Always end with `SELECT * FROM final`
- Use Jinja comments `{# #}` for model documentation (excluded from compiled SQL), not SQL `--` for docs

## Column Conventions

**Ordering:**

IDs / Keys → Strings → Numerics → Booleans → Dates → Timestamps → Audit columns

**Naming:**

| Type | Convention | Examples |
|------|-----------|----------|
| Boolean | `is_` or `has_` prefix | `is_active`, `has_charging_point` |
| Timestamp | `_at` suffix | `ingested_at`, `last_updated_at` |
| Date | `_date` suffix | `report_date` |
| JSON-sourced float | cast explicitly to `FLOAT64` | `latitude`, `longitude` |
| Raw payload passthrough | `payload` (the full JSON blob as ingested) | `payload` |

**Audit columns** (required on `table`/`incremental` materializations, not views):

| Column | Value |
|--------|-------|
| `_dbt_updated_at` | `CURRENT_TIMESTAMP()` |

## BigQuery-Specific Notes

- Staging models are `view` — always fresh, zero storage cost
- Mart models use `table` or `incremental` depending on query volume
- Incremental strategy: `merge` with `unique_key`; use `_dbt_updated_at` as the watermark column
- For incremental, use `{{ this }}` self-reference for the watermark (not hardcoded date offsets):
  ```sql
  {% if is_incremental() %}
      and ingested_at > (select max(ingested_at) from {{ this }})
  {% endif %}
  ```
- No `dist`/`sort` keys — those are Redshift concepts. BigQuery handles distribution automatically

## Raw Source Layout

Raw tables land in `{BQ_DATASET_RAW}` (e.g. `dev_raw` or `prod_raw`). Each table has this schema:

| Column | Type | Notes |
|--------|------|-------|
| `batch_id` | STRING | Dagster run ID — unique per materialization |
| `source_name` | STRING | e.g. `ev_charger_availability` |
| `ingested_at` | TIMESTAMP | Written by the ingestion asset |
| `payload` | JSON | Full API response, untouched |

Staging models unnest `payload` via `JSON_VALUE` / `JSON_QUERY_ARRAY`. The `batch_id` and `ingested_at` columns propagate to every staging row.

## Testing by Layer

| Layer | Required Tests | Severity |
|-------|---------------|----------|
| **Staging** | `not_null` on `batch_id`, `ingested_at`. `unique` on natural key if one exists | `error` |
| **Marts** | `unique` + `not_null` on PKs. `relationships` for FKs to staging | `error` |

Source freshness is configured in `sources.yml` — set `warn_after` / `error_after` to match the ingestion schedule (currently 30-min cron).

## YML Properties Template

```yaml
version: 2

models:
  - name: stg_ev_charger_availability
    description: >
      One row per charger location per ingestion batch. Explodes the raw
      ev_charger_availability payload JSON into queryable columns.
    columns:
      - name: batch_id
        description: Dagster run ID from the ingestion asset.
        data_tests:
          - not_null
      - name: ingested_at
        description: Timestamp when this batch was written to BigQuery.
        data_tests:
          - not_null
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Filtering/joining inside import CTEs | Import CTEs must be pure `SELECT * FROM ref()/source()`. Move logic to a separate CTE |
| `source()` in a mart model | Marts reference staging via `ref()` only — never `source()` directly |
| Uppercase SQL keywords | This repo uses lowercase keywords (`select`, `from`, `where`) — enforced by SQLFluff |
| Hardcoded BigQuery project/dataset | Always use `ref()` or `source()` — dbt resolves the target from `profiles.yml` |
| Forgetting `AS` on aliases | Always use the `AS` keyword for column and table aliases |
| Trailing comma after last `SELECT` column | SQLFluff will error — no trailing commas |
| `longtitude` typo in source | The LTA API has a typo — the raw field is `longtitude`. Map it to `longitude` in staging |
| Business logic in staging | Staging = unnest + rename. Business logic belongs in marts |
