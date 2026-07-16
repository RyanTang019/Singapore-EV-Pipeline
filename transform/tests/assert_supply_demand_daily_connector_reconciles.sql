-- Supply is unknown when no snapshot qualifies. Otherwise counts are
-- non-negative, connector states reconcile, and defined rates are bounded.
select *
from {{ ref('fct_supply_demand_daily') }}
where
    latest_qualified_location_count < 0
    or latest_qualified_connector_count < 0
    or latest_qualified_connector_density_per_sqkm < 0
    or available_connectors_observed < 0
    or occupied_connectors_observed < 0
    or unavailable_connectors_observed < 0
    or unknown_connectors_observed < 0
    or total_connectors_observed < 0
    or average_available_connectors_per_qualified_snapshot < 0
    or effective_available_connectors_per_sqkm < 0
    or daily_availability_rate not between 0 and 1
    or daily_occupied_rate not between 0 and 1
    or daily_unavailable_rate not between 0 and 1
    or daily_unknown_rate not between 0 and 1
    or total_connectors_observed != (
        available_connectors_observed
        + occupied_connectors_observed
        + unavailable_connectors_observed
        + unknown_connectors_observed
    )
    or (
        total_connectors_observed > 0
        and abs(
            daily_availability_rate
            + daily_occupied_rate
            + daily_unavailable_rate
            + daily_unknown_rate
            - 1.0
        ) > 1e-9
    )
    or (
        total_connectors_observed = 0
        and (
            daily_availability_rate is not null
            or daily_occupied_rate is not null
            or daily_unavailable_rate is not null
            or daily_unknown_rate is not null
        )
    )
    or (
        qualified_daily_snapshot_count = 0
        and (
            latest_qualified_location_count is not null
            or latest_qualified_connector_count is not null
            or latest_qualified_connector_density_per_sqkm is not null
            or available_connectors_observed is not null
            or occupied_connectors_observed is not null
            or unavailable_connectors_observed is not null
            or unknown_connectors_observed is not null
            or total_connectors_observed is not null
            or average_available_connectors_per_qualified_snapshot is not null
            or effective_available_connectors_per_sqkm is not null
        )
    )
    or (
        qualified_daily_snapshot_count > 0
        and (
            latest_qualified_location_count is null
            or latest_qualified_connector_count is null
            or latest_qualified_connector_density_per_sqkm is null
            or available_connectors_observed is null
            or occupied_connectors_observed is null
            or unavailable_connectors_observed is null
            or unknown_connectors_observed is null
            or total_connectors_observed is null
            or average_available_connectors_per_qualified_snapshot is null
            or effective_available_connectors_per_sqkm is null
        )
    )
