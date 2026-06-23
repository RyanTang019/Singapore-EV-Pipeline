---
description: SQL style standards for the transform/ directory, enforced by SQLFluff (BigQuery dialect)
globs: transform/**/*.sql
---

# SQL Style

Apply these rules strictly when generating, refactoring, or reviewing SQL in `transform/`.

## Capitalisation

Use **lowercase** for all:
- Keywords: `select`, `from`, `where`, `join`, `on`, `group by`, `order by`, `limit`, `with`, `as`, `and`, `or`, `not`, `null`, `true`, `false`, `distinct`, `case`, `when`, `then`, `else`, `end`
- Functions: `count()`, `sum()`, `max()`, `current_timestamp()`, `json_value()`, `json_query()`, `json_query_array()`, `cast()`, `coalesce()`, `unnest()`
- Data types: `string`, `int64`, `float64`, `bool`, `timestamp`, `date`, `json`
- Literals: `null`, `true`, `false`

Use **consistent case** for identifiers (column names, table names, CTE names) — lowercase throughout.

## Indentation

- 4 spaces per level. No tabs.
- `select`, `from`, `where`, `join`, `group by`, `order by`, `having`, `limit` — all at the same indent level as the CTE body
- Columns in a `select` list: indent 4 spaces relative to `select`
- `on` clause of a `join`: indent 4 spaces relative to the `join` line
- `when`/`then`/`else`/`end` in a `case`: indent 4 spaces relative to `case`
- Do NOT indent `join` lines themselves — they sit at the same level as `from`

```sql
with source as (
    select * from {{ source('raw', 'ev_charger_availability') }}
),

final as (
    select
        batch_id,
        ingested_at,
        json_value(location, '$.name')                         as name,
        cast(json_value(location, '$.latitude') as float64)    as latitude
    from source
    join other_table
        on source.batch_id = other_table.batch_id
    where ingested_at is not null
)

select * from final
```

## Aliasing

- Always use the `as` keyword for column and table aliases — never implicit aliasing
- `column_expression as alias_name`, not `column_expression alias_name`
- Scalar expressions (e.g. `count(*) as total`) must also use `as`

## Commas

- Trailing commas: comma goes at the **end of the line**, not the start of the next
- No trailing comma after the **last** column in a `select` list (SQLFluff errors on this)

```sql
-- correct
select
    batch_id,
    ingested_at,
    name

-- wrong
select
    batch_id
    ,ingested_at   -- leading comma
    ,name,         -- trailing comma on last item
```

## Subqueries

- Subqueries are forbidden inside `join` clauses — use a CTE instead
- Subqueries in `from` clauses are allowed but prefer CTEs for readability

## BigQuery-Specific

- JSON extraction: `json_value()` for scalars, `json_query()` for objects/arrays, `json_query_array()` for arrays to unnest
- Always `cast` JSON-extracted numerics: `cast(json_value(...) as float64)`
- Unnesting: `from table, unnest(json_query_array(payload, '$.key')) as element`
- No Redshift syntax: no `ilike`, no `::` type casts (use `cast()`), no `distkey`/`sortkey`
