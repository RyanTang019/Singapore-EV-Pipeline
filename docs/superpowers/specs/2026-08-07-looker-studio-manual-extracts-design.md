# Looker Studio Manual Extracts Design

## Goal

Reduce recurring BigQuery query costs for the Singapore EV Infrastructure Operations dashboard by serving charts from manually refreshed Looker Studio extracts. The dashboard should continue to open on the latest seven days while the historical extracts retain all available history at a compressed grain.

## Target report

- Work only in `Singapore EV Infrastructure Operations — Extracts (BQ kept)` (`4aeb2d89-ea36-4542-ad8c-e461fd62ba27`).
- Leave the original report and the earlier experimental copy unchanged.
- Keep every existing BigQuery data source attached to the target report, even after verification.

## Source strategy

Add a separate embedded Extract Data source for each BigQuery source that is moved off direct querying. Name it `<existing source name> — Manual Extract` where the Looker Studio editor permits renaming.

Current-state sources may use raw extracts because they contain only the latest snapshot. Include the dimensions, metrics, keys, timestamps, calculated-field inputs, and filter fields that their charts actually use. Do not add fields merely because Looker Studio displays them as blue metrics.

Large historical sources use an aggregated extract with this target grain:

`date × hour × planning area`

Retain all available dates. Add only the dimensions needed for dashboard grouping and filtering and the measures required by the existing charts. Additive counts are summed. Rates and percentages are calculated from the summed numerator and denominator, rather than averaged from row-level percentages. For example, weighted EV availability is `SUM(available connectors) / SUM(total connectors)`.

The dashboard's date control remains set to the latest seven days by default. Users may widen it to any period retained in the extract without querying BigQuery.

## Refresh behaviour

- Disable **Auto update** on every extract.
- The extract changes only when an editor deliberately opens its connection and runs the extract/save action.
- Refreshing an extract is expected to query BigQuery once; normal dashboard viewing should use the stored extract.

## Migration flow

1. Inventory the fields and calculated fields used by each chart tied to a BigQuery source.
2. Create and save a separate manual extract with the required fields.
3. Verify its row/size limits and confirm that Auto update is disabled.
4. Test the extract against the same seven-day range as the existing chart.
5. Switch compatible charts to the verified extract.
6. Leave the corresponding BigQuery source attached and available for rollback.

No BigQuery source may be deleted, removed, replaced in place, or detached.

## Verification and rollback

For each migrated chart:

- Compare scorecards, totals, time-series shape, date controls, and filters with the BigQuery-backed version over the same seven-day range.
- Confirm that calculated fields still produce the same result.
- Confirm that the extract reports **Working** and has Auto update disabled.
- Confirm that every original BigQuery source is still present in **Manage added data sources**.

If an extract exceeds Looker Studio's 750,000-row or 100 MB limit, or a chart cannot reproduce its BigQuery result, do not switch that chart. Leave it on its BigQuery source and report the specific limitation. Because the old sources remain attached, rollback consists only of changing the affected chart back to its original source.

## Success criteria

- The target report keeps all seven existing BigQuery sources.
- Migrated charts use separate manual extracts with Auto update disabled.
- Historical extracts retain all available history at hourly planning-area grain.
- The report continues to open on a seven-day date range.
- Verified seven-day results match the existing BigQuery-backed charts.
- No source, report, chart, or calculated field is deleted.
