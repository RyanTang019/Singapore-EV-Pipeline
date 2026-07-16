"""Generate controlled MP2019 planning-area population seeds from SingStat C020125.

The stable ``population_release_key`` is SHA-256 over these exact UTF-8 bytes, with
literal ASCII unit separators and no trailing newline::

    population_release_v1\x1f<source_dataset_id>\x1f<source_reference_date>\x1f\
<planning_geography_version>\x1f<source_sha256>

Publication/retrieval dates, the display name, URL, and filename are deliberately excluded from
that data-identity key. The tool is deterministic, makes no network request, and never reads the
clock. All release metadata must be supplied explicitly.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

APPROVED_SOURCE_DATASET_ID = (
    "singstat_c020125_resident_population_planning_area_subzone_dwelling"
)
GEOGRAPHY_VERSION = "MP2019"
RELEASE_KEY_VERSION = "population_release_v1"
SOURCE_AREA_HEADER = "Planning Area/Subzone of Residence"
LOWER_SNAKE_CASE = re.compile(r"^[a-z0-9_]+$")
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")

POPULATION_FIELDNAMES = [
    "population_release_key",
    "population_year",
    "planning_area",
    "resident_population",
]
METADATA_FIELDNAMES = [
    "population_release_key",
    "population_year",
    "source_reference_date",
    "source_published_date",
    "source_retrieved_date",
    "planning_geography_version",
    "national_resident_population",
    "max_national_reconciliation_difference",
    "expected_planning_area_row_count",
    "generated_planning_area_population_total",
    "source_dataset_id",
    "source_name",
    "source_url",
    "source_filename",
    "source_sha256",
]


@dataclass(frozen=True)
class GenerationConfig:
    """Explicit, reviewed release metadata and validation bounds."""

    population_year: int
    source_reference_date: date
    source_published_date: date
    source_retrieved_date: date
    planning_geography_version: str
    national_resident_population: int
    expected_planning_area_row_count: int
    source_dataset_id: str
    source_name: str
    source_url: str
    max_national_reconciliation_difference: int


@dataclass(frozen=True)
class ParsedSource:
    population_rows: list[dict[str, Any]]
    national_resident_population: int


@dataclass(frozen=True)
class GeneratedOutputs:
    population_csv: bytes
    metadata_csv: bytes
    release_key: str
    source_sha256: str
    population_output_sha256: str
    metadata_output_sha256: str
    row_count: int
    generated_population_total: int
    national_reconciliation_difference: int
    source_national_reconciliation_difference: int


def sha256_bytes(value: bytes) -> str:
    """Return a lower-case SHA-256 hex digest."""

    return hashlib.sha256(value).hexdigest()


def parse_population_value(raw_value: str) -> int | None:
    """Parse reviewed SingStat notation without coercing unknown tokens."""

    value = raw_value.strip()
    if value == "-":
        return 0
    if value.lower() == "na":
        return None
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError(f"unknown population notation: {raw_value!r}")


def _find_measure(rows: Sequence[Sequence[str]]) -> tuple[int, int]:
    for row_index, row in enumerate(rows):
        if row and row[0].strip() == SOURCE_AREA_HEADER:
            total_columns = [
                index for index, label in enumerate(row) if index > 0 and label.strip() == "Total"
            ]
            if not total_columns:
                raise ValueError("source header has no all-dwelling Total measure")
            return row_index, total_columns[0]
    raise ValueError(f"source header {SOURCE_AREA_HEADER!r} was not found")


def parse_source(source_bytes: bytes) -> ParsedSource:
    """Select national and planning-area totals from the reviewed hierarchical CSV."""

    try:
        text = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("source must be UTF-8 encoded") from exc

    rows = list(csv.reader(io.StringIO(text)))
    header_index, total_column = _find_measure(rows)
    population_rows: list[dict[str, Any]] = []
    national_population: int | None = None

    for row in rows[header_index + 1 :]:
        if not row:
            continue
        raw_name = row[0]
        normalized_name = raw_name.strip()
        if normalized_name == "Total":
            if len(row) <= total_column:
                raise ValueError("national total row is missing the all-dwelling Total measure")
            national_population = parse_population_value(row[total_column])
            if national_population is None:
                raise ValueError("national resident population cannot be na")
            continue

        # Official subzone rows are indented. Planning-area aggregate rows are not.
        if raw_name != raw_name.lstrip() or not normalized_name.endswith(" - Total"):
            continue
        if len(row) <= total_column:
            raise ValueError(f"planning-area row {normalized_name!r} is missing Total measure")

        planning_area = normalized_name[: -len(" - Total")].strip().upper()
        if not planning_area:
            raise ValueError("planning-area total row has an empty planning-area name")
        population_rows.append(
            {
                "planning_area": planning_area,
                "resident_population": parse_population_value(row[total_column]),
            }
        )

    if national_population is None:
        raise ValueError("source national Total row was not found")
    if not population_rows:
        raise ValueError("source contains no planning-area Total rows")

    names = [row["planning_area"] for row in population_rows]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate planning areas: {duplicates}")
    population_rows.sort(key=lambda row: row["planning_area"])
    return ParsedSource(population_rows, national_population)


def load_expected_areas(seed_path: Path) -> set[str]:
    """Load the exact conformed planning-area natural keys from the boundary seed."""

    with seed_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    areas = {row["planning_area"].strip().upper() for row in rows}
    if not areas or "" in areas:
        raise ValueError(f"expected-area seed is empty or invalid: {seed_path}")
    if len(areas) != len(rows):
        raise ValueError(f"expected-area seed contains duplicate planning areas: {seed_path}")
    return areas


def validate_exact_areas(
    population_rows: Sequence[dict[str, Any]], expected_areas: set[str]
) -> None:
    """Require exact source/dimension area-set equality."""

    actual_areas = {str(row["planning_area"]) for row in population_rows}
    missing = sorted(expected_areas - actual_areas)
    unknown = sorted(actual_areas - expected_areas)
    if missing or unknown:
        raise ValueError(f"planning-area membership mismatch: missing={missing}; unknown={unknown}")


def validate_metadata(
    config: GenerationConfig, *, require_approved_dataset_id: bool = False
) -> None:
    """Validate explicit release metadata and compatibility locks."""

    if config.planning_geography_version != GEOGRAPHY_VERSION:
        raise ValueError(f"planning_geography_version must be {GEOGRAPHY_VERSION}")
    if config.population_year != config.source_reference_date.year:
        raise ValueError("population_year must equal the source reference date year")
    if not (
        config.source_reference_date
        <= config.source_published_date
        <= config.source_retrieved_date
    ):
        raise ValueError("dates must satisfy reference <= published <= retrieved")
    if not LOWER_SNAKE_CASE.fullmatch(config.source_dataset_id):
        raise ValueError("source_dataset_id must be lower snake case")
    if require_approved_dataset_id and config.source_dataset_id != APPROVED_SOURCE_DATASET_ID:
        raise ValueError(
            "initial source_dataset_id must equal the owner-approved C020125 repository identity"
        )
    for field_name in ("source_name", "source_url"):
        if not getattr(config, field_name).strip():
            raise ValueError(f"{field_name} is required")
    if config.national_resident_population <= 0:
        raise ValueError("national_resident_population must be positive")
    if config.expected_planning_area_row_count <= 0:
        raise ValueError("expected_planning_area_row_count must be positive")
    if config.max_national_reconciliation_difference < 0:
        raise ValueError("max_national_reconciliation_difference must be non-negative")


def canonical_release_payload(
    source_dataset_id: str,
    source_reference_date: date,
    planning_geography_version: str,
    source_sha256: str,
) -> bytes:
    """Build the versioned release-identity payload using literal unit separators."""

    if not SHA256_HEX.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be 64 lower-case hexadecimal characters")
    fields = (
        RELEASE_KEY_VERSION,
        source_dataset_id,
        source_reference_date.isoformat(),
        planning_geography_version,
        source_sha256,
    )
    return "\x1f".join(fields).encode("utf-8")


def generate_release_key(
    source_dataset_id: str,
    source_reference_date: date,
    planning_geography_version: str,
    source_sha256: str,
) -> str:
    """Generate the stable, lower-case SHA-256 population release key."""

    return sha256_bytes(
        canonical_release_payload(
            source_dataset_id,
            source_reference_date,
            planning_geography_version,
            source_sha256,
        )
    )


def serialize_csv(rows: Iterable[dict[str, Any]], fieldnames: Sequence[str]) -> bytes:
    """Serialize deterministic UTF-8 CSV with LF line endings."""

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def validate_generated_pair(
    population_rows: Sequence[dict[str, Any]], metadata_rows: Sequence[dict[str, Any]]
) -> None:
    """Validate grain and bidirectional release-key agreement for a generated pair."""

    if len(metadata_rows) != 1:
        raise ValueError(f"expected one metadata row, got {len(metadata_rows)}")
    metadata_key = str(metadata_rows[0].get("population_release_key", ""))
    population_keys = {str(row.get("population_release_key", "")) for row in population_rows}
    if population_keys != {metadata_key}:
        raise ValueError(
            f"release key mismatch between population and metadata rows: "
            f"population={sorted(population_keys)} metadata={metadata_key!r}"
        )
    if not SHA256_HEX.fullmatch(metadata_key):
        raise ValueError("population_release_key must be 64 lower-case hexadecimal characters")
    grains = [
        (str(row.get("population_release_key", "")), str(row.get("planning_area", "")))
        for row in population_rows
    ]
    if len(grains) != len(set(grains)):
        raise ValueError("generated population rows contain a duplicate release/area grain")


def _validate_source_and_config(
    parsed: ParsedSource, expected_areas: set[str], config: GenerationConfig
) -> tuple[int, int, int]:
    validate_metadata(config)
    validate_exact_areas(parsed.population_rows, expected_areas)
    if len(expected_areas) != config.expected_planning_area_row_count:
        raise ValueError(
            "expected_planning_area_row_count does not match the injected expected-area set"
        )
    if len(parsed.population_rows) != config.expected_planning_area_row_count:
        raise ValueError(
            f"expected {config.expected_planning_area_row_count} planning-area rows, "
            f"got {len(parsed.population_rows)}"
        )

    values = [row["resident_population"] for row in parsed.population_rows]
    if any(value is not None and value < 0 for value in values):
        raise ValueError("resident_population must be non-negative when present")
    if config.population_year == 2025 and "TAMPINES" in expected_areas:
        tampines = next(
            row["resident_population"]
            for row in parsed.population_rows
            if row["planning_area"] == "TAMPINES"
        )
        if tampines != 290090:
            raise ValueError(f"2025 Tampines validation anchor failed: got {tampines!r}")

    generated_total = sum(value for value in values if value is not None)
    national_difference = abs(generated_total - config.national_resident_population)
    source_national_difference = abs(generated_total - parsed.national_resident_population)
    maximum = config.max_national_reconciliation_difference
    if national_difference > maximum:
        raise ValueError(
            f"generated total differs from national anchor by {national_difference}, "
            f"above reviewed maximum {maximum}"
        )
    if source_national_difference > maximum:
        raise ValueError(
            f"generated total differs from source national total by {source_national_difference}, "
            f"above reviewed maximum {maximum}"
        )
    return generated_total, national_difference, source_national_difference


def build_outputs(
    source_bytes: bytes,
    expected_areas: set[str],
    config: GenerationConfig,
    source_filename: str,
) -> GeneratedOutputs:
    """Parse, validate, and fully serialize both controlled seed outputs."""

    if not source_filename.strip():
        raise ValueError("source_filename is required")
    parsed = parse_source(source_bytes)
    generated_total, national_difference, source_national_difference = (
        _validate_source_and_config(parsed, expected_areas, config)
    )
    source_sha256 = sha256_bytes(source_bytes)
    release_key = generate_release_key(
        config.source_dataset_id,
        config.source_reference_date,
        config.planning_geography_version,
        source_sha256,
    )

    population_rows = [
        {
            "population_release_key": release_key,
            "population_year": config.population_year,
            "planning_area": row["planning_area"],
            "resident_population": row["resident_population"],
        }
        for row in parsed.population_rows
    ]
    population_rows.sort(
        key=lambda row: (
            row["population_year"],
            row["population_release_key"],
            row["planning_area"],
        )
    )
    metadata_rows = [
        {
            "population_release_key": release_key,
            "population_year": config.population_year,
            "source_reference_date": config.source_reference_date.isoformat(),
            "source_published_date": config.source_published_date.isoformat(),
            "source_retrieved_date": config.source_retrieved_date.isoformat(),
            "planning_geography_version": config.planning_geography_version,
            "national_resident_population": config.national_resident_population,
            "max_national_reconciliation_difference": (
                config.max_national_reconciliation_difference
            ),
            "expected_planning_area_row_count": config.expected_planning_area_row_count,
            "generated_planning_area_population_total": generated_total,
            "source_dataset_id": config.source_dataset_id,
            "source_name": config.source_name,
            "source_url": config.source_url,
            "source_filename": source_filename,
            "source_sha256": source_sha256,
        }
    ]
    validate_generated_pair(population_rows, metadata_rows)
    population_csv = serialize_csv(population_rows, POPULATION_FIELDNAMES)
    metadata_csv = serialize_csv(metadata_rows, METADATA_FIELDNAMES)

    # Validate the serialized representation, not only the in-memory structures.
    validate_generated_pair(
        list(csv.DictReader(io.StringIO(population_csv.decode("utf-8")))),
        list(csv.DictReader(io.StringIO(metadata_csv.decode("utf-8")))),
    )
    return GeneratedOutputs(
        population_csv=population_csv,
        metadata_csv=metadata_csv,
        release_key=release_key,
        source_sha256=source_sha256,
        population_output_sha256=sha256_bytes(population_csv),
        metadata_output_sha256=sha256_bytes(metadata_csv),
        row_count=len(population_rows),
        generated_population_total=generated_total,
        national_reconciliation_difference=national_difference,
        source_national_reconciliation_difference=source_national_difference,
    )


def _write_fsynced_temp(payload: bytes, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        return Path(handle.name)


def _make_backup(destination: Path) -> Path | None:
    if not destination.exists():
        return None
    descriptor, backup_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".backup",
    )
    os.close(descriptor)
    backup = Path(backup_name)
    shutil.copy2(destination, backup)
    with backup.open("rb") as handle:
        os.fsync(handle.fileno())
    return backup


def write_output_pair(
    population_csv: bytes,
    metadata_csv: bytes,
    population_path: Path,
    metadata_path: Path,
) -> None:
    """Validate then replace both outputs, rolling back caught partial replacements."""

    if population_path.resolve() == metadata_path.resolve():
        raise ValueError("population and metadata outputs must use different paths")

    population_temp = _write_fsynced_temp(population_csv, population_path)
    metadata_temp = _write_fsynced_temp(metadata_csv, metadata_path)
    population_backup: Path | None = None
    metadata_backup: Path | None = None
    try:
        validate_generated_pair(
            list(csv.DictReader(io.StringIO(population_temp.read_text(encoding="utf-8")))),
            list(csv.DictReader(io.StringIO(metadata_temp.read_text(encoding="utf-8")))),
        )
        if population_temp.read_bytes() != population_csv:
            raise OSError("population temporary file failed byte validation")
        if metadata_temp.read_bytes() != metadata_csv:
            raise OSError("metadata temporary file failed byte validation")

        population_backup = _make_backup(population_path)
        metadata_backup = _make_backup(metadata_path)
        os.replace(population_temp, population_path)
        os.replace(metadata_temp, metadata_path)
    except Exception:
        if population_backup is not None:
            os.replace(population_backup, population_path)
            population_backup = None
        elif population_path.exists() and not population_temp.exists():
            population_path.unlink()
        if metadata_backup is not None:
            os.replace(metadata_backup, metadata_path)
            metadata_backup = None
        elif metadata_path.exists() and not metadata_temp.exists():
            metadata_path.unlink()
        raise
    finally:
        for path in (
            population_temp,
            metadata_temp,
            population_backup,
            metadata_backup,
        ):
            if path is not None:
                path.unlink(missing_ok=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--reference-date", type=date.fromisoformat, required=True)
    parser.add_argument("--published-date", type=date.fromisoformat, required=True)
    parser.add_argument("--retrieved-date", type=date.fromisoformat, required=True)
    parser.add_argument("--geography-version", required=True)
    parser.add_argument("--national-resident-population", type=int, required=True)
    parser.add_argument("--expected-planning-area-row-count", type=int, required=True)
    parser.add_argument("--source-dataset-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--max-national-reconciliation-difference", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = GenerationConfig(
        population_year=args.year,
        source_reference_date=args.reference_date,
        source_published_date=args.published_date,
        source_retrieved_date=args.retrieved_date,
        planning_geography_version=args.geography_version,
        national_resident_population=args.national_resident_population,
        expected_planning_area_row_count=args.expected_planning_area_row_count,
        source_dataset_id=args.source_dataset_id,
        source_name=args.source_name,
        source_url=args.source_url,
        max_national_reconciliation_difference=args.max_national_reconciliation_difference,
    )
    validate_metadata(config, require_approved_dataset_id=True)
    repo_root = Path(__file__).resolve().parent.parent
    expected_areas = load_expected_areas(repo_root / "transform" / "seeds" / "planning_areas.csv")
    outputs = build_outputs(
        args.input.read_bytes(),
        expected_areas,
        config,
        args.input.name,
    )
    write_output_pair(
        outputs.population_csv,
        outputs.metadata_csv,
        args.output,
        args.metadata_output,
    )

    print(f"Input SHA-256: {outputs.source_sha256}")
    print(f"Population output SHA-256: {outputs.population_output_sha256}")
    print(f"Metadata output SHA-256: {outputs.metadata_output_sha256}")
    print(f"Population release key: {outputs.release_key}")
    print(f"Planning-area row count: {outputs.row_count}")
    print(f"Generated planning-area population total: {outputs.generated_population_total}")
    print(f"National resident population anchor: {config.national_resident_population}")
    print(
        "National reconciliation difference / allowed maximum: "
        f"{outputs.national_reconciliation_difference} / "
        f"{config.max_national_reconciliation_difference}"
    )
    print(
        "Source-national reconciliation difference: "
        f"{outputs.source_national_reconciliation_difference}"
    )
    print("Unmatched planning areas: missing=[]; unknown=[]")


if __name__ == "__main__":
    main()
