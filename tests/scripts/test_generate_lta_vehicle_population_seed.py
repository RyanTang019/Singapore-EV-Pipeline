from __future__ import annotations

import csv
import io
import runpy
import sys
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.generate_lta_vehicle_population_seed as generator  # noqa: E402
from scripts.generate_lta_vehicle_population_seed import (  # noqa: E402
    APPROVED_SOURCE_DATASET_ID,
    OBSERVATION_FIELDNAMES,
    RELEASE_FIELDNAMES,
    GenerationConfig,
    build_outputs,
    canonical_release_payload,
    generate_release_key,
    load_classification,
    parse_archive,
    parse_rows,
    print_audit,
    validate,
    validate_generated_pair,
    write_output_pair,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "lta"
    / "monthly_vehicle_population_by_fuel_minimal.zip"
)
MEMBER_NAME = "M09-Vehs_by_Fuel_Type.csv"
CLASSIFICATION_FIELDNAMES = [
    "source_fuel_type",
    "powertrain_group",
    "is_bev",
    "is_phev",
    "is_plug_in_vehicle",
    "classification_version",
]
CLASSIFICATION_ROWS = [
    ("Petrol", "combustion", "false", "false", "false", "lta_m09_powertrain_v1"),
    ("Diesel", "combustion", "false", "false", "false", "lta_m09_powertrain_v1"),
    ("Petrol-CNG", "combustion", "false", "false", "false", "lta_m09_powertrain_v1"),
    ("CNG", "combustion", "false", "false", "false", "lta_m09_powertrain_v1"),
    (
        "Petrol-Electric",
        "non_plug_in_hybrid",
        "false",
        "false",
        "false",
        "lta_m09_powertrain_v1",
    ),
    (
        "Diesel-Electric",
        "non_plug_in_hybrid",
        "false",
        "false",
        "false",
        "lta_m09_powertrain_v1",
    ),
    ("Electric", "battery_electric", "true", "false", "true", "lta_m09_powertrain_v1"),
    (
        "Petrol-Electric (Plug-In)",
        "plug_in_hybrid",
        "false",
        "true",
        "true",
        "lta_m09_powertrain_v1",
    ),
    (
        "Diesel-Electric (Plug-In)",
        "plug_in_hybrid",
        "false",
        "true",
        "true",
        "lta_m09_powertrain_v1",
    ),
]


@pytest.fixture
def classification_path(tmp_path: Path) -> Path:
    return _write_classification(tmp_path / "classification.csv")


def _write_classification(
    path: Path,
    rows: list[tuple[str, str, str, str, str, str]] | None = None,
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CLASSIFICATION_FIELDNAMES)
        writer.writerows(CLASSIFICATION_ROWS if rows is None else rows)
    return path


def _config(**overrides: object) -> GenerationConfig:
    config = GenerationConfig(
        source_retrieved_date=date(2026, 7, 23),
        source_catalog_update_month="2026-06",
        expected_first_month="2024-01",
        expected_latest_month="2025-01",
        source_dataset_id=APPROVED_SOURCE_DATASET_ID,
        source_name="Monthly Motor Vehicle Population Statistics by Type of Fuel Used",
        source_url="https://example.test/lta-m09.zip",
    )
    return replace(config, **overrides)


def _zip_bytes(
    csv_bytes: bytes,
    *,
    member_name: str = MEMBER_NAME,
    extra_member: tuple[str, bytes] | None = None,
    stored: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    compression = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr(member_name, csv_bytes)
        if extra_member is not None:
            archive.writestr(*extra_member)
    return buffer.getvalue()


def _mutate_csv(
    csv_bytes: bytes,
    *,
    data_row: int = 0,
    **changes: str,
) -> bytes:
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    header = rows[0]
    for field, value in changes.items():
        rows[data_row + 1][header.index(field)] = value
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _filter_csv(csv_bytes: bytes, keep) -> bytes:
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(rows[0])
    writer.writerows(row for row in rows[1:] if keep(dict(zip(rows[0], row, strict=True))))
    return buffer.getvalue().encode("utf-8")


def _csv_rows(output: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(output.decode("utf-8"))))


def _build(
    classification_path: Path,
    *,
    archive_bytes: bytes | None = None,
    config: GenerationConfig | None = None,
):
    return build_outputs(
        FIXTURE.read_bytes() if archive_bytes is None else archive_bytes,
        load_classification(classification_path),
        _config() if config is None else config,
        FIXTURE.name,
    )


def test_fixture_contains_single_exact_member_and_header():
    csv_bytes = parse_archive(FIXTURE.read_bytes())

    assert csv_bytes.splitlines()[0] == b"month,category,type,number"
    assert len(parse_rows(csv_bytes)) >= 13 * 5


def test_fixture_helper_rebuilds_committed_zip_byte_for_byte():
    fixture_builder = runpy.run_path(str(FIXTURE.with_name("make_fixture.py")))

    assert fixture_builder["build_zip_bytes"]() == FIXTURE.read_bytes()


def test_parse_archive_rejects_wrong_basename_extra_members_and_mutated_header():
    csv_bytes = parse_archive(FIXTURE.read_bytes())

    with pytest.raises(ValueError, match="M09-Vehs_by_Fuel_Type.csv"):
        parse_archive(_zip_bytes(csv_bytes, member_name="m09.csv"))
    with pytest.raises(ValueError, match="exactly one archive member"):
        parse_archive(_zip_bytes(csv_bytes, extra_member=("README.txt", b"extra")))
    with pytest.raises(ValueError, match="exact header"):
        parse_archive(_zip_bytes(csv_bytes.replace(b"month,", b"Month,", 1)))


def test_parse_rows_emits_calendar_month_end_including_leap_day():
    observations = parse_rows(parse_archive(FIXTURE.read_bytes()))

    assert {row.month_end for row in observations if row.month_end.year == 2024} >= {
        date(2024, 1, 31),
        date(2024, 2, 29),
    }


@pytest.mark.parametrize("month", ["", "2024-1", "24-01", "2024-13", "2024-01-01"])
def test_parse_rows_rejects_malformed_month(month: str):
    csv_bytes = _mutate_csv(parse_archive(FIXTURE.read_bytes()), month=month)

    with pytest.raises(ValueError, match="month.*YYYY-MM"):
        parse_rows(csv_bytes)


@pytest.mark.parametrize(
    "token",
    ["", "-1", "1.5", "unknown", "1,00", "1,0000", "01,000", "1,,000", ",100", "0,000"],
)
def test_parse_rows_rejects_unreviewed_count_tokens(token: str):
    csv_bytes = _mutate_csv(parse_archive(FIXTURE.read_bytes()), number=token)

    with pytest.raises(ValueError, match="count token"):
        parse_rows(csv_bytes)


@pytest.mark.parametrize(("token", "expected"), [("1,000", 1000), ("572,226", 572226)])
def test_parse_rows_accepts_strictly_grouped_integer_tokens(token: str, expected: int):
    csv_bytes = _mutate_csv(parse_archive(FIXTURE.read_bytes()), number=token)

    observation = parse_rows(csv_bytes)[0]

    assert observation.source_value_token == token
    assert observation.vehicle_population == expected
    assert observation.source_value_status == "reported_numeric"


def test_parse_rows_rejects_duplicate_source_grain():
    csv_bytes = parse_archive(FIXTURE.read_bytes())
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    rows.append(rows[1])
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)

    with pytest.raises(ValueError, match="duplicate source grain"):
        parse_rows(buffer.getvalue().encode())


def test_validate_rejects_missing_month_and_missing_category(classification_path: Path):
    csv_bytes = parse_archive(FIXTURE.read_bytes())
    classification = load_classification(classification_path)
    without_month = _filter_csv(csv_bytes, lambda row: row["month"] != "2024-02")
    without_taxis = _filter_csv(
        csv_bytes,
        lambda row: not (row["month"] == "2024-02" and row["category"] == "Taxis"),
    )

    with pytest.raises(ValueError, match="continuous months"):
        validate(parse_rows(without_month), classification, _config())
    with pytest.raises(ValueError, match="missing vehicle categories.*Taxis"):
        validate(parse_rows(without_taxis), classification, _config())


def test_validate_enforces_expected_first_and_latest_month(classification_path: Path):
    observations = parse_rows(parse_archive(FIXTURE.read_bytes()))
    classification = load_classification(classification_path)

    with pytest.raises(ValueError, match="expected first month"):
        validate(
            observations,
            classification,
            _config(expected_first_month="2023-12"),
        )
    with pytest.raises(ValueError, match="expected latest month"):
        validate(
            observations,
            classification,
            _config(expected_latest_month="2025-02"),
        )


def test_validate_requires_exact_observed_and_classified_fuel_label_sets(
    classification_path: Path,
    tmp_path: Path,
):
    observations = parse_rows(parse_archive(FIXTURE.read_bytes()))
    missing_cng = _write_classification(
        tmp_path / "missing.csv",
        [row for row in CLASSIFICATION_ROWS if row[0] != "CNG"],
    )
    extra_steam = _write_classification(
        tmp_path / "extra.csv",
        CLASSIFICATION_ROWS
        + [
            (
                "Steam",
                "combustion",
                "false",
                "false",
                "false",
                "lta_m09_powertrain_v1",
            )
        ],
    )

    with pytest.raises(ValueError, match=r"unknown=\['CNG'\]"):
        validate(observations, load_classification(missing_cng), _config())
    with pytest.raises(ValueError, match=r"missing=\['Steam'\]"):
        validate(observations, load_classification(extra_steam), _config())


def test_vehicle_type_normalization_is_exact_and_unmapped_category_fails():
    observations = parse_rows(parse_archive(FIXTURE.read_bytes()))

    assert {
        row.source_vehicle_category: row.vehicle_type for row in observations
    } == {
        "Cars": "cars",
        "Taxis": "taxis",
        "Motor-cycles": "motorcycles",
        "Goods & Other Vehicles": "goods_and_other_vehicles",
        "Buses": "buses",
    }
    csv_bytes = _mutate_csv(
        parse_archive(FIXTURE.read_bytes()),
        category="Goods and Other Vehicles",
    )
    with pytest.raises(ValueError, match="unmapped vehicle category"):
        parse_rows(csv_bytes)


def test_dash_and_numeric_zero_are_preserved_with_distinct_statuses(
    classification_path: Path,
):
    rows = _csv_rows(_build(classification_path).population_csv)
    dash = next(row for row in rows if row["source_value_token"] == "-")
    numeric_zero = next(row for row in rows if row["source_value_token"] == "0")

    assert dash["vehicle_population"] == "0"
    assert dash["source_value_status"] == "source_dash_zero"
    assert numeric_zero["vehicle_population"] == "0"
    assert numeric_zero["source_value_status"] == "reported_numeric"


def test_audit_lists_every_dash_row_and_bev_phev_classification(
    classification_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    output = _build(classification_path)

    print_audit(output, load_classification(classification_path))

    audit = capsys.readouterr().out
    assert "2024-06-30 | Buses | Petrol-CNG | is_bev=false | is_phev=false" in audit
    assert audit.count("Dash row:") == 1


def test_release_payload_and_pinned_hash_are_exact():
    payload = canonical_release_payload("dataset_id", "a" * 64, date(2025, 1, 31))

    assert payload == (
        b"lta_m09_release_v1\x1fdataset_id\x1f"
        + b"a" * 64
        + b"\x1f2025-01-31"
    )
    assert not payload.endswith(b"\n")
    assert generate_release_key(
        "dataset_id", "a" * 64, date(2025, 1, 31)
    ) == "a731066aca0437b501fd7c950536de38f4653772eb5b3a747c5ffc1415598544"


def test_release_key_ignores_audit_metadata_and_zip_repackaging(
    classification_path: Path,
):
    csv_bytes = parse_archive(FIXTURE.read_bytes())
    base = _build(classification_path)
    repacked = _build(
        classification_path,
        archive_bytes=_zip_bytes(
            csv_bytes,
            member_name=f"nested/{MEMBER_NAME}",
            stored=True,
        ),
    )

    assert repacked.release_key == base.release_key
    assert repacked.archive_sha256 != base.archive_sha256
    for changed in (
        _config(source_retrieved_date=date(2026, 7, 24)),
        _config(source_catalog_update_month="2026-07"),
    ):
        assert _build(classification_path, config=changed).release_key == base.release_key


def test_release_key_changes_with_csv_dataset_id_or_latest_month():
    base = generate_release_key("dataset_id", "a" * 64, date(2025, 1, 31))

    assert generate_release_key("dataset_id", "b" * 64, date(2025, 1, 31)) != base
    assert generate_release_key("another_dataset", "a" * 64, date(2025, 1, 31)) != base
    assert generate_release_key("dataset_id", "a" * 64, date(2025, 2, 28)) != base


def test_outputs_are_deterministic_sorted_lf_terminated_and_have_exact_columns(
    classification_path: Path,
):
    first = _build(classification_path)
    second = _build(classification_path)
    rows = _csv_rows(first.population_csv)

    assert first.population_csv == second.population_csv
    assert first.metadata_csv == second.metadata_csv
    assert b"\r\n" not in first.population_csv + first.metadata_csv
    assert first.population_csv.endswith(b"\n")
    assert first.metadata_csv.endswith(b"\n")
    assert list(rows[0]) == OBSERVATION_FIELDNAMES
    assert list(_csv_rows(first.metadata_csv)[0]) == RELEASE_FIELDNAMES
    assert [
        (row["month_end"], row["vehicle_type"], row["source_fuel_type"]) for row in rows
    ] == sorted(
        (row["month_end"], row["vehicle_type"], row["source_fuel_type"]) for row in rows
    )


def test_generated_pair_has_bidirectional_release_key_and_reconciled_metadata(
    classification_path: Path,
):
    output = _build(classification_path)
    population_rows = _csv_rows(output.population_csv)
    metadata_rows = _csv_rows(output.metadata_csv)
    metadata = metadata_rows[0]

    assert {row["source_release_key"] for row in population_rows} == {output.release_key}
    assert metadata["source_release_key"] == output.release_key
    assert metadata["source_row_count"] == str(len(population_rows))
    assert metadata["source_vehicle_category_count"] == "5"
    assert metadata["source_fuel_type_count"] == "9"
    validate_generated_pair(population_rows, metadata_rows)

    metadata["source_release_key"] = "0" * 64
    with pytest.raises(ValueError, match="release key mismatch"):
        validate_generated_pair(population_rows, metadata_rows)


def test_write_output_pair_replaces_both_and_requires_distinct_paths(
    classification_path: Path,
    tmp_path: Path,
):
    first = _build(classification_path)
    csv_bytes = _mutate_csv(parse_archive(FIXTURE.read_bytes()), data_row=10, number="999")
    second = _build(classification_path, archive_bytes=_zip_bytes(csv_bytes))
    population_path = tmp_path / "population.csv"
    metadata_path = tmp_path / "metadata.csv"

    write_output_pair(
        first.population_csv,
        first.metadata_csv,
        population_path,
        metadata_path,
    )
    write_output_pair(
        second.population_csv,
        second.metadata_csv,
        population_path,
        metadata_path,
    )
    assert population_path.read_bytes() == second.population_csv
    assert metadata_path.read_bytes() == second.metadata_csv
    with pytest.raises(ValueError, match="different paths"):
        write_output_pair(
            second.population_csv,
            second.metadata_csv,
            population_path,
            population_path,
        )


@pytest.mark.parametrize("existing_output", ["population", "metadata"])
def test_write_output_pair_refuses_a_one_sided_existing_pair(
    classification_path: Path,
    tmp_path: Path,
    existing_output: str,
):
    output = _build(classification_path)
    population_path = tmp_path / "population.csv"
    metadata_path = tmp_path / "metadata.csv"
    existing_path = (
        population_path if existing_output == "population" else metadata_path
    )
    missing_path = (
        metadata_path if existing_output == "population" else population_path
    )
    existing_path.write_bytes(b"reviewed existing output\n")

    with pytest.raises(ValueError, match="both exist or neither"):
        write_output_pair(
            output.population_csv,
            output.metadata_csv,
            population_path,
            metadata_path,
        )

    assert existing_path.read_bytes() == b"reviewed existing output\n"
    assert not missing_path.exists()


def test_write_output_pair_cleans_up_if_second_temp_creation_fails(
    classification_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = _build(classification_path)
    population_path = tmp_path / "population.csv"
    metadata_path = tmp_path / "metadata.csv"
    real_write_temp = generator._write_fsynced_temp
    calls = 0

    def fail_second_temp(payload: bytes, destination: Path) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second temporary-file failure")
        return real_write_temp(payload, destination)

    monkeypatch.setattr(generator, "_write_fsynced_temp", fail_second_temp)
    with pytest.raises(OSError, match="simulated second"):
        write_output_pair(
            output.population_csv,
            output.metadata_csv,
            population_path,
            metadata_path,
        )

    assert {path.name for path in tmp_path.iterdir()} == {"classification.csv"}


def test_write_output_pair_rolls_back_a_partial_replacement(
    classification_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    first = _build(classification_path)
    csv_bytes = _mutate_csv(parse_archive(FIXTURE.read_bytes()), data_row=10, number="999")
    second = _build(classification_path, archive_bytes=_zip_bytes(csv_bytes))
    population_path = tmp_path / "population.csv"
    metadata_path = tmp_path / "metadata.csv"
    write_output_pair(
        first.population_csv,
        first.metadata_csv,
        population_path,
        metadata_path,
    )
    real_replace = generator.os.replace
    failed = False

    def fail_metadata_replace(source, destination):
        nonlocal failed
        if (
            not failed
            and Path(destination) == metadata_path
            and Path(source).suffix == ".tmp"
        ):
            failed = True
            raise OSError("simulated metadata replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(generator.os, "replace", fail_metadata_replace)
    with pytest.raises(OSError, match="simulated"):
        write_output_pair(
            second.population_csv,
            second.metadata_csv,
            population_path,
            metadata_path,
        )

    assert population_path.read_bytes() == first.population_csv
    assert metadata_path.read_bytes() == first.metadata_csv


def test_historical_restatement_changes_observation_hash_and_release_key(
    classification_path: Path,
):
    base = _build(classification_path)
    csv_bytes = parse_archive(FIXTURE.read_bytes())
    restated_csv = _mutate_csv(csv_bytes, data_row=10, number="999")
    restated = _build(classification_path, archive_bytes=_zip_bytes(restated_csv))

    assert restated.population_output_sha256 != base.population_output_sha256
    assert restated.release_key != base.release_key


def test_cli_wires_all_reviewed_inputs_and_writes_the_pair(
    classification_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    population_path = tmp_path / "population.csv"
    metadata_path = tmp_path / "metadata.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_lta_vehicle_population_seed.py",
            "--input",
            str(FIXTURE),
            "--output",
            str(population_path),
            "--metadata-output",
            str(metadata_path),
            "--classification-input",
            str(classification_path),
            "--retrieved-date",
            "2026-07-23",
            "--catalog-update-month",
            "2026-06",
            "--expected-first-month",
            "2024-01",
            "--expected-latest-month",
            "2025-01",
            "--source-dataset-id",
            APPROVED_SOURCE_DATASET_ID,
        ],
    )

    generator.main()

    validate_generated_pair(
        _csv_rows(population_path.read_bytes()),
        _csv_rows(metadata_path.read_bytes()),
    )
    assert "Archive SHA-256:" in capsys.readouterr().out
