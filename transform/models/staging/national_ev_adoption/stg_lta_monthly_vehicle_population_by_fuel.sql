{{ config(materialized='view') }}

{#
    Explicitly typed view over the controlled LTA M09 observation seed. Types and keys only:
    fuel classification and any aggregation belong to the fact, not to staging.
#}

select
    cast(source_release_key as string) as source_release_key,
    cast(month_end as date) as month_end,
    cast(source_vehicle_category as string) as source_vehicle_category,
    cast(vehicle_type as string) as vehicle_type,
    cast(source_fuel_type as string) as source_fuel_type,
    cast(source_value_token as string) as source_value_token,
    cast(vehicle_population as int64) as vehicle_population,
    cast(source_value_status as string) as source_value_status,
    to_hex(
        md5(
            concat(
                cast(month_end as string),
                '|',
                cast(vehicle_type as string),
                '|',
                cast(source_fuel_type as string)
            )
        )
    ) as vehicle_population_key
from {{ ref('lta_monthly_vehicle_population_by_fuel') }}
