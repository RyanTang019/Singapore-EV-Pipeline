{# stg_ev_charger_availability + planning_area (macro on lat/lon) + SGT time
   features. Grain unchanged (connector per snapshot). View. #}

{{ config(materialized='view') }}

select
    *,
    {{ planning_area_of('longitude', 'latitude') }} as planning_area,
    {{ time_features('snapshot_time') }}
from {{ ref('stg_ev_charger_availability') }}
