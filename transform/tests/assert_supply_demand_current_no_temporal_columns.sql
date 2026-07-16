{% set report_relation = ref('rpt_supply_demand_gap_current') %}
{% set columns_relation %}
    `{{ report_relation.database }}.{{ report_relation.schema }}.INFORMATION_SCHEMA.COLUMNS`
{% endset %}

-- Looker date controls must not suppress this current-slice page.
select
    column_name,
    data_type
from {{ columns_relation }}
where
    table_name
    = '{{ report_relation.identifier }}'
    and data_type in ('DATE', 'DATETIME', 'TIMESTAMP')
