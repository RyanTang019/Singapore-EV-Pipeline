{#
    Source-grain integrity for the staged LTA M09 observations.

    The declared grain must be unique, and source_vehicle_category to vehicle_type must be a
    bijection: the surrogate key hashes the normalized type while grain uniqueness is asserted on
    the source label, which is only safe while the mapping stays one-to-one. An accepted_values
    test cannot catch this — it would pass if two source categories both normalized to `cars`.
#}

with observations as (

    select
        month_end,
        source_vehicle_category,
        vehicle_type,
        source_fuel_type
    from {{ ref('stg_lta_monthly_vehicle_population_by_fuel') }}

),

duplicate_grain as (

    select
        'duplicate_source_grain' as failure_type,
        concat(
            cast(month_end as string),
            '|',
            source_vehicle_category,
            '|',
            source_fuel_type
        ) as failure_key,
        count(*) as failure_count
    from observations
    group by month_end, source_vehicle_category, source_fuel_type
    having count(*) > 1

),

category_maps_to_many_types as (

    select
        'source_category_maps_to_many_vehicle_types' as failure_type,
        source_vehicle_category as failure_key,
        count(distinct vehicle_type) as failure_count
    from observations
    group by source_vehicle_category
    having count(distinct vehicle_type) > 1

),

vehicle_type_maps_from_many_categories as (

    select
        'vehicle_type_maps_from_many_source_categories' as failure_type,
        vehicle_type as failure_key,
        count(distinct source_vehicle_category) as failure_count
    from observations
    group by vehicle_type
    having count(distinct source_vehicle_category) > 1

)

select
    failure_type,
    failure_key,
    failure_count
from duplicate_grain
union all
select
    failure_type,
    failure_key,
    failure_count
from category_maps_to_many_types
union all
select
    failure_type,
    failure_key,
    failure_count
from vehicle_type_maps_from_many_categories
