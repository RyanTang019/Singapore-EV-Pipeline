{% macro time_features(ts) %}
    date({{ ts }}, 'Asia/Singapore') as snapshot_date,
    extract(hour from {{ ts }} at time zone 'Asia/Singapore') as hour_of_day,
    cast(format_date('%u', date({{ ts }}, 'Asia/Singapore')) as int64) as day_of_week
{% endmacro %}
