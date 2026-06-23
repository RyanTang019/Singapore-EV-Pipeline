-- Singular data-integrity test: selects rows that violate the availability math.
-- dbt convention: a test passes when this query returns ZERO rows.
-- Catches sign/division errors, a rate outside [0,1], counts drifting apart, or empty groups.

select *
from {{ ref('fct_ev_location_availability') }}
where availability_rate < 0
   or availability_rate > 1
   or available_connectors > total_connectors
   or total_connectors < 1
