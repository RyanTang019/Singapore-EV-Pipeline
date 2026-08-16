{#
    The 2026-05 mart month must match the spec 3.2 acceptance anchors for all
    six scopes' total/BEV/PHEV stock. Deliberately NOT filtered by
    source_release_key: a routine monthly refresh with unchanged history keeps
    enforcing the anchor (a release-key filter would turn this into a vacuous
    zero-row test), while an approved LTA restatement of 2026-05 must update
    the spec and these expected values in the same reviewed pull request.
    Empty result = pass.
#}

with expected as (

    select
        'cars' as vehicle_scope,
        654691 as total_vehicle_population,
        62653 as bev_population,
        2915 as phev_population
    union all
    select
        'taxis' as vehicle_scope,
        12276 as total_vehicle_population,
        599 as bev_population,
        0 as phev_population
    union all
    select
        'motorcycles' as vehicle_scope,
        153542 as total_vehicle_population,
        420 as bev_population,
        0 as phev_population
    union all
    select
        'goods_and_other_vehicles' as vehicle_scope,
        143060 as total_vehicle_population,
        7428 as bev_population,
        2 as phev_population
    union all
    select
        'buses' as vehicle_scope,
        18384 as total_vehicle_population,
        890 as bev_population,
        46 as phev_population
    union all
    select
        'all_vehicles' as vehicle_scope,
        981953 as total_vehicle_population,
        71990 as bev_population,
        2963 as phev_population

),

actual as (

    select
        vehicle_scope,
        total_vehicle_population,
        bev_population,
        phev_population
    from {{ ref('mart_national_ev_adoption_monthly') }}
    where month_end = date '2026-05-31'

)

select
    expected.vehicle_scope,
    expected.total_vehicle_population as expected_total,
    actual.total_vehicle_population as actual_total,
    expected.bev_population as expected_bev,
    actual.bev_population as actual_bev,
    expected.phev_population as expected_phev,
    actual.phev_population as actual_phev
from expected
left join actual
    on expected.vehicle_scope = actual.vehicle_scope
where
    actual.vehicle_scope is null
    or actual.total_vehicle_population
    is distinct from expected.total_vehicle_population
    or actual.bev_population is distinct from expected.bev_population
    or actual.phev_population is distinct from expected.phev_population
