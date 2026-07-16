from __future__ import annotations

import csv
import hashlib
import io
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.generate_planning_area_population_seed import (  # noqa: E402
    APPROVED_SOURCE_DATASET_ID,
    GenerationConfig,
    build_outputs,
    canonical_release_payload,
    generate_release_key,
    parse_population_value,
    parse_source,
    validate_generated_pair,
    validate_metadata,
    write_output_pair,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "singstat"
    / "planning_area_population_minimal.csv"
)
EXPECTED_AREAS = {
    "ANG MO KIO",
    "CENTRAL WATER CATCHMENT",
    "CHANGI BAY",
    "PUNGGOL",
    "TAMPINES",
}


def _config(**overrides) -> GenerationConfig:
    config = GenerationConfig(
        population_year=2025,
        source_reference_date=date(2025, 6, 30),
        source_published_date=date(2026, 6, 30),
        source_retrieved_date=date(2026, 7, 16),
        planning_geography_version="MP2019",
        national_resident_population=448800,
        expected_planning_area_row_count=5,
        source_dataset_id=APPROVED_SOURCE_DATASET_ID,
        source_name="Reviewed fixture dataset",
        source_url="https://example.test/C020125",
        max_national_reconciliation_difference=30,
    )
    return replace(config, **overrides)


def _csv_rows(output: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(output.decode("utf-8"))))


def test_parse_source_selects_only_planning_area_totals_and_first_total_measure():
    parsed = parse_source(FIXTURE.read_bytes())

    assert [row["planning_area"] for row in parsed.population_rows] == [
        "ANG MO KIO",
        "CENTRAL WATER CATCHMENT",
        "CHANGI BAY",
        "PUNGGOL",
        "TAMPINES",
    ]
    assert {row["planning_area"]: row["resident_population"] for row in parsed.population_rows} == {
        "ANG MO KIO": 158720,
        "CENTRAL WATER CATCHMENT": 0,
        "CHANGI BAY": 0,
        "PUNGGOL": None,
        "TAMPINES": 290090,
    }
    assert parsed.national_resident_population == 448830


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("123", 123), ("0", 0), ("-", 0), ("na", None), (" NA ", None)],
)
def test_parse_population_value_handles_reviewed_notation(raw: str, expected: int | None):
    assert parse_population_value(raw) == expected


@pytest.mark.parametrize("raw", ["", "nec", "nes", "unknown", "12.5", "1,000"])
def test_parse_population_value_rejects_unknown_notation(raw: str):
    with pytest.raises(ValueError, match="unknown population notation"):
        parse_population_value(raw)


def test_exact_area_validation_distinguishes_nil_from_omitted_area():
    parsed = parse_source(FIXTURE.read_bytes())
    central = next(
        row for row in parsed.population_rows if row["planning_area"] == "CENTRAL WATER CATCHMENT"
    )
    assert central["resident_population"] == 0

    with pytest.raises(ValueError, match=r"missing=\['BEDOK'\]"):
        build_outputs(
            FIXTURE.read_bytes(),
            expected_areas=EXPECTED_AREAS | {"BEDOK"},
            config=replace(_config(), expected_planning_area_row_count=6),
            source_filename=FIXTURE.name,
        )


def test_unknown_and_duplicate_planning_areas_fail_closed():
    source = FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown=\['UNKNOWN AREA'\]"):
        build_outputs(
            source.replace("Punggol - Total", "Unknown Area - Total").encode(),
            expected_areas=EXPECTED_AREAS,
            config=_config(),
            source_filename=FIXTURE.name,
        )

    with pytest.raises(ValueError, match="duplicate planning areas.*TAMPINES"):
        parse_source(source.replace("Punggol - Total", "Tampines - Total").encode())


def test_metadata_validation_requires_mp2019_and_ordered_explicit_dates():
    with pytest.raises(ValueError, match="MP2019"):
        validate_metadata(replace(_config(), planning_geography_version="MP2025"))
    with pytest.raises(ValueError, match="reference.*published.*retrieved"):
        validate_metadata(
            replace(
                _config(),
                source_published_date=date(2025, 6, 29),
                source_retrieved_date=date(2025, 6, 28),
            )
        )
    with pytest.raises(ValueError, match="source_name"):
        validate_metadata(replace(_config(), source_name=""))


def test_release_payload_and_hash_are_exact_and_stable():
    payload = canonical_release_payload(
        "dataset_id", date(2025, 6, 30), "MP2019", "a" * 64
    )
    assert payload == (
        b"population_release_v1\x1fdataset_id\x1f2025-06-30\x1fMP2019\x1f"
        + b"a" * 64
    )
    assert not payload.endswith(b"\n")
    assert generate_release_key(
        "dataset_id", date(2025, 6, 30), "MP2019", "a" * 64
    ) == "c95e535849345ef3cdad392ee4c36c3b1ffcd2043ea720fc7a0a5cfc69916362"


def test_release_key_ignores_non_identity_metadata_and_changes_with_identity():
    source = FIXTURE.read_bytes()
    base = build_outputs(source, EXPECTED_AREAS, _config(), FIXTURE.name)

    for changed in [
        replace(_config(), source_retrieved_date=date(2026, 7, 17)),
        replace(_config(), source_published_date=date(2026, 7, 1)),
        replace(_config(), source_name="Renamed display label"),
        replace(_config(), source_url="https://example.test/moved"),
    ]:
        assert build_outputs(source, EXPECTED_AREAS, changed, "renamed.csv").release_key == (
            base.release_key
        )

    identity_variants = [
        (source + b" ", _config()),
        (source, replace(_config(), source_reference_date=date(2025, 7, 1))),
        (source, replace(_config(), planning_geography_version="MP2018")),
        (source, replace(_config(), source_dataset_id="another_dataset")),
    ]
    for changed_source, changed_config in identity_variants:
        assert generate_release_key(
            changed_config.source_dataset_id,
            changed_config.source_reference_date,
            changed_config.planning_geography_version,
            hashlib.sha256(changed_source).hexdigest(),
        ) != base.release_key


def test_outputs_are_sorted_lf_terminated_and_byte_identical():
    first = build_outputs(FIXTURE.read_bytes(), EXPECTED_AREAS, _config(), FIXTURE.name)
    second = build_outputs(FIXTURE.read_bytes(), EXPECTED_AREAS, _config(), FIXTURE.name)

    assert first.population_csv == second.population_csv
    assert first.metadata_csv == second.metadata_csv
    assert b"\r\n" not in first.population_csv + first.metadata_csv
    assert first.population_csv.endswith(b"\n")
    assert [row["planning_area"] for row in _csv_rows(first.population_csv)] == sorted(
        EXPECTED_AREAS
    )


def test_generated_population_and_metadata_carry_the_same_release_key():
    output = build_outputs(FIXTURE.read_bytes(), EXPECTED_AREAS, _config(), FIXTURE.name)
    population_rows = _csv_rows(output.population_csv)
    metadata_rows = _csv_rows(output.metadata_csv)

    assert {row["population_release_key"] for row in population_rows} == {output.release_key}
    assert metadata_rows[0]["population_release_key"] == output.release_key
    validate_generated_pair(population_rows, metadata_rows)

    metadata_rows[0]["population_release_key"] = "0" * 64
    with pytest.raises(ValueError, match="release key mismatch"):
        validate_generated_pair(population_rows, metadata_rows)


def test_write_output_pair_is_deterministic_and_replaces_both_files(tmp_path: Path):
    output = build_outputs(FIXTURE.read_bytes(), EXPECTED_AREAS, _config(), FIXTURE.name)
    population_path = tmp_path / "population.csv"
    metadata_path = tmp_path / "metadata.csv"

    write_output_pair(
        output.population_csv,
        output.metadata_csv,
        population_path,
        metadata_path,
    )
    first_bytes = (population_path.read_bytes(), metadata_path.read_bytes())
    write_output_pair(
        output.population_csv,
        output.metadata_csv,
        population_path,
        metadata_path,
    )
    assert (population_path.read_bytes(), metadata_path.read_bytes()) == first_bytes
