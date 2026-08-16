{#
    The committed powertrain policy seed must equal the complete nine-row mapping locked in
    design section 3.5 — exact powertrain_group, BEV, PHEV, plug-in, and version values — compared
    in both directions so neither an edited row nor an added one can slip through. The observed and
    classified fuel-label sets are compared both ways too, so a new source label fails here rather
    than silently dropping out of the fact's inner join.

    Because the comparison is row-exact against section 3.5, it also pins is_bev and is_phev as
    mutually exclusive and is_plug_in_vehicle as is_bev or is_phev.
#}

with expected_policy as (

    {#
        One struct per section 3.5 row, in section 3.5 order. Only the first struct names its
        fields; the rest are positional, so field order is
        (source_fuel_type, powertrain_group, is_bev, is_phev, is_plug_in_vehicle).
    #}
    select
        expected_row.source_fuel_type,
        expected_row.powertrain_group,
        expected_row.is_bev,
        expected_row.is_phev,
        expected_row.is_plug_in_vehicle,
        'lta_m09_powertrain_v1' as classification_version
    from unnest([
        struct(
            'Petrol' as source_fuel_type,
            'combustion' as powertrain_group,
            false as is_bev,
            false as is_phev,
            false as is_plug_in_vehicle
        ),
        struct('Diesel', 'combustion', false, false, false),
        struct('Petrol-Electric', 'non_plug_in_hybrid', false, false, false),
        struct(
            'Petrol-Electric (Plug-In)', 'plug_in_hybrid', false, true, true
        ),
        struct('Petrol-CNG', 'combustion', false, false, false),
        struct('CNG', 'combustion', false, false, false),
        struct('Electric', 'battery_electric', true, false, true),
        struct('Diesel-Electric', 'non_plug_in_hybrid', false, false, false),
        struct(
            'Diesel-Electric (Plug-In)', 'plug_in_hybrid', false, true, true
        )
    ]) as expected_row

),

actual_policy as (

    select
        source_fuel_type,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version
    from {{ ref('lta_fuel_type_classification') }}

),

expected_policy_not_in_seed as (

    select
        source_fuel_type,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version
    from expected_policy
    except distinct
    select
        source_fuel_type,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version
    from actual_policy

),

seed_policy_not_in_expected as (

    select
        source_fuel_type,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version
    from actual_policy
    except distinct
    select
        source_fuel_type,
        powertrain_group,
        is_bev,
        is_phev,
        is_plug_in_vehicle,
        classification_version
    from expected_policy

),

staged_fuel_types as (

    select distinct source_fuel_type
    from {{ ref('stg_lta_monthly_vehicle_population_by_fuel') }}

),

staged_not_classified as (

    select source_fuel_type from staged_fuel_types
    except distinct
    select source_fuel_type from actual_policy

),

classified_not_staged as (

    select source_fuel_type from actual_policy
    except distinct
    select source_fuel_type from staged_fuel_types

)

select
    'policy_row_missing_from_seed' as failure_type,
    source_fuel_type as failure_key
from expected_policy_not_in_seed
union all
select
    'unexpected_policy_row_in_seed' as failure_type,
    source_fuel_type as failure_key
from seed_policy_not_in_expected
union all
select
    'staged_fuel_label_not_classified' as failure_type,
    source_fuel_type as failure_key
from staged_not_classified
union all
select
    'classified_fuel_label_not_staged' as failure_type,
    source_fuel_type as failure_key
from classified_not_staged
