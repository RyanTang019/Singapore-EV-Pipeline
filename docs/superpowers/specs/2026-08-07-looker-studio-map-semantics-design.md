# Looker Studio Map Semantics Design

## Goal

Make every operational map in `Singapore EV Infrastructure Operations — Extracts (BQ kept)` use the Supply–Demand Gap map's red, neutral, and green/teal palette while preserving intuitive meaning: favorable conditions are green/teal and unfavorable conditions are red.

## Target report

- Report: `Singapore EV Infrastructure Operations — Extracts (BQ kept)`
- Report ID: `4aeb2d89-ea36-4542-ad8c-e461fd62ba27`
- Change map styling only. Do not change data sources, fields, metrics, filters, calculated fields, chart types, or extract schedules.
- Keep every original BigQuery source and every extract attached to the report.

## Reference palette

Use the existing Supply–Demand Gap map as the source of truth:

- Unfavorable: `#D94C4C` (`rgb(217, 76, 76)`)
- Neutral midpoint: `#F4F6F8` (`rgb(244, 246, 248)`)
- Favorable: `#008C95` (`rgb(0, 140, 149)`)
- No data: `#D9E3F0` (`rgb(217, 227, 240)`)

## Semantic mapping

### Live EV map

The color metric is availability rate. Higher availability is favorable.

- Minimum: unfavorable red
- Midpoint: neutral
- Maximum: favorable green/teal

### Live Carparks map

The color metric is available lots. More reported available lots is favorable.

- Minimum: unfavorable red
- Midpoint: neutral
- Maximum: favorable green/teal

### Live Traffic map

The color metric is congestion rate. Higher congestion is unfavorable.

- Minimum: favorable green/teal
- Midpoint: neutral
- Maximum: unfavorable red

### Supply–Demand Gap map

Leave the existing palette and direction unchanged. It is the reference map.

## Verification

After changing the three map palettes:

1. Confirm all four operational maps render without errors.
2. Confirm each map retains its original data source, location or geospatial field, tooltip, size metric, and color metric.
3. Confirm the operational scorecards still match their audited values.
4. Confirm the Supply–Demand Gap map was not modified.
5. Confirm all seven extracts still have Auto update disabled and all original BigQuery sources remain attached.

## Success criteria

- Green/teal consistently means favorable conditions.
- Red consistently means unfavorable conditions.
- Neutral and no-data colors match the Supply–Demand Gap map.
- No data, source, field, schedule, or chart behavior changes.
