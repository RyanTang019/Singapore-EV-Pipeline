-- Fails on any out-of-range measure: rate must be 0–1, mean band 1–8 when present.
select traffic_congestion_key, congested_link_rate, mean_speed_band
from {{ ref('fct_traffic_congestion') }}
where congested_link_rate < 0 or congested_link_rate > 1
   or (mean_speed_band is not null and (mean_speed_band < 1 or mean_speed_band > 8))
