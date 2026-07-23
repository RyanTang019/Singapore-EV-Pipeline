"""Generate deterministic LTA M09 vehicle-population and release-metadata seeds.

The tool is a controlled boundary around a manually retrieved official ZIP. It
does not access the network or clock, and every audit date is supplied
explicitly. Data identity is derived from the exact CSV member bytes, not the
ZIP container::

    lta_m09_release_v1\x1f<source_dataset_id>\x1f<csv_sha256>\x1f<latest_month_end>
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

APPROVED_SOURCE_DATASET_ID = "lta_m09_monthly_vehicle_population_by_fuel"
SOURCE_NAME = "Monthly Motor Vehicle Population Statistics by Type of Fuel Used"
SOURCE_URL = (
    "https://datamall.lta.gov.sg/content/dam/datamall/datasets/Facts_Figures/"
    "Vehicle%20Population/Monthly%20Motor%20Vehicle%20Population%20Statistics%20"
    "by%20Type%20of%20Fuel%20Used.zip"
)
CSV_FILENAME = "M09-Vehs_by_Fuel_Type.csv"
RELEASE_KEY_VERSION = "lta_m09_release_v1"
CLASSIFICATION_VERSION = "lta_m09_powertrain_v1"
SOURCE_HEADER = ["month", "category", "type", "number"]
LOWER_SNAKE_CASE = re.compile(r"^[a-z0-9_]+$")
MONTH_TOKEN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
UNSIGNED_INTEGER = re.compile(r"^[0-9]+$")
GROUPED_UNSIGNED_INTEGER = re.compile(r"^[1-9][0-9]{0,2}(?:,[0-9]{3})+$")
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")

VEHICLE_TYPE_BY_CATEGORY = {
    "Cars": "cars",
    "Taxis": "taxis",
    "Motor-cycles": "motorcycles",
    "Goods & Other Vehicles": "goods_and_other_vehicles",
    "Buses": "buses",
}
APPROVED_CATEGORIES = frozenset(VEHICLE_TYPE_BY_CATEGORY)

OBSERVATION_FIELDNAMES = [
    "source_release_key",
    "month_end",
    "source_vehicle_category",
    "vehicle_type",
    "source_fuel_type",
    "source_value_token",
    "vehicle_population",
    "source_value_status",
]
RELEASE_FIELDNAMES = [
    "source_release_key",
    "source_dataset_id",
    "source_name",
    "source_url",
    "source_catalog_update_month",
    "source_retrieved_date",
    "first_month_end",
    "latest_month_end",
    "source_row_count",
    "source_vehicle_category_count",
    "source_fuel_type_count",
    "archive_filename",
    "archive_sha256",
    "csv_filename",
    "csv_sha256",
]
CLASSIFICATION_FIELDNAMES = [
    "source_fuel_type",
    "powertrain_group",
    "is_bev",
    "is_phev",
    "is_plug_in_vehicle",
    "classification_version",
]
POWERTRAIN_GROUPS = {
    "combustion",
    "non_plug_in_hybrid",
    "battery_electric",
    "plug_in_hybrid",
}


@dataclass(frozen=True)
class Observation:
    """A parsed source observation before release identity is attached."""

    month_end: date
    source_vehicle_category: str
    vehicle_type: str
    source_fuel_type: str
    source_value_token: str
    vehicle_population: int
    source_value_status: str


@dataclass(frozen=True)
class Classification:
    """Reviewed policy for one exact source fuel label."""

    source_fuel_type: str
    powertrain_group: str
    is_bev: bool
    is_phev: bool
    is_plug_in_vehicle: bool
    classification_version: str


@dataclass(frozen=True)
class GenerationConfig:
    """Explicit audit metadata and reviewed month bounds."""

    source_retrieved_date: date
    source_catalog_update_month: str
    expected_first_month: str
    expected_latest_month: str
    source_dataset_id: str
    source_name: str = SOURCE_NAME
    source_url: str = SOURCE_URL


@dataclass(frozen=True)
class ValidationSummary:
    """Validated source shape used to construct release metadata and audit output."""

    first_month_end: date
    latest_month_end: date
    month_count: int
    source_vehicle_category_count: int
    source_fuel_type_count: int
    latest_month_category_totals: dict[str, int]
    dash_rows: tuple[Observation, ...]


@dataclass(frozen=True)
class GeneratedOutputs:
    """Both serialized seed outputs and their audit facts."""

    population_csv: bytes
    metadata_csv: bytes
    release_key: str
    archive_sha256: str
    csv_sha256: str
    population_output_sha256: str
    metadata_output_sha256: str
    row_count: int
    month_count: int
    source_vehicle_category_count: int
    source_fuel_type_count: int
    first_month_end: date
    latest_month_end: date
    latest_month_category_totals: dict[str, int]
    dash_rows: tuple[Observation, ...]


def sha256_bytes(value: bytes) -> str:
    """Return a lower-case SHA-256 hex digest."""

    return hashlib.sha256(value).hexdigest()


def _month_end(raw_month: str, *, field_name: str = "month") -> date:
    if not MONTH_TOKEN.fullmatch(raw_month):
        raise ValueError(f"{field_name} must use exact YYYY-MM notation: {raw_month!r}")
    year, month = (int(part) for part in raw_month.split("-"))
    return date(year, month, calendar.monthrange(year, month)[1])


def _iter_month_ends(first_month: str, latest_month: str) -> list[date]:
    first = _month_end(first_month, field_name="expected first month")
    latest = _month_end(latest_month, field_name="expected latest month")
    if first > latest:
        raise ValueError("expected first month must not follow expected latest month")
    months: list[date] = []
    year, month = first.year, first.month
    while (year, month) <= (latest.year, latest.month):
        months.append(date(year, month, calendar.monthrange(year, month)[1]))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return months


def parse_archive(zip_bytes: bytes) -> bytes:
    """Return the one canonical M09 CSV member after exact structure validation."""

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) != 1:
                raise ValueError(
                    f"expected exactly one archive member, got {len(members)}"
                )
            member = members[0]
            if PurePosixPath(member.filename).name != CSV_FILENAME:
                raise ValueError(
                    f"archive member basename must be {CSV_FILENAME!r}, "
                    f"got {member.filename!r}"
                )
            csv_bytes = archive.read(member)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("input must be a readable ZIP archive") from exc

    try:
        rows = csv.reader(io.StringIO(csv_bytes.decode("utf-8"), newline=""))
        header = next(rows)
    except (UnicodeDecodeError, StopIteration, csv.Error) as exc:
        raise ValueError("M09 CSV must be non-empty UTF-8 CSV") from exc
    if header != SOURCE_HEADER:
        raise ValueError(f"M09 CSV must have exact header {','.join(SOURCE_HEADER)}")
    return csv_bytes


def parse_rows(csv_bytes: bytes) -> list[Observation]:
    """Parse exact M09 rows without fuzzy label or token coercion."""

    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("M09 CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != SOURCE_HEADER:
        raise ValueError(f"M09 CSV must have exact header {','.join(SOURCE_HEADER)}")

    observations: list[Observation] = []
    grains: set[tuple[date, str, str]] = set()
    try:
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(row[field] is None for field in SOURCE_HEADER):
                raise ValueError(f"row {row_number} does not have exactly four fields")
            raw_month = str(row["month"])
            category = str(row["category"])
            fuel_type = str(row["type"])
            count_token = str(row["number"])
            month_end = _month_end(raw_month)
            try:
                vehicle_type = VEHICLE_TYPE_BY_CATEGORY[category]
            except KeyError as exc:
                raise ValueError(
                    f"unmapped vehicle category at row {row_number}: {category!r}"
                ) from exc
            if not fuel_type:
                raise ValueError(f"source fuel type is blank at row {row_number}")
            if count_token == "-":
                vehicle_population = 0
                source_value_status = "source_dash_zero"
            elif UNSIGNED_INTEGER.fullmatch(count_token):
                vehicle_population = int(count_token)
                source_value_status = "reported_numeric"
            elif GROUPED_UNSIGNED_INTEGER.fullmatch(count_token):
                vehicle_population = int(count_token.replace(",", ""))
                source_value_status = "reported_numeric"
            else:
                raise ValueError(
                    f"unknown count token at row {row_number}: {count_token!r}"
                )

            grain = (month_end, category, fuel_type)
            if grain in grains:
                raise ValueError(
                    "duplicate source grain: "
                    f"{month_end.isoformat()} / {category} / {fuel_type}"
                )
            grains.add(grain)
            observations.append(
                Observation(
                    month_end=month_end,
                    source_vehicle_category=category,
                    vehicle_type=vehicle_type,
                    source_fuel_type=fuel_type,
                    source_value_token=count_token,
                    vehicle_population=vehicle_population,
                    source_value_status=source_value_status,
                )
            )
    except csv.Error as exc:
        raise ValueError("M09 CSV contains malformed CSV data") from exc
    if not observations:
        raise ValueError("M09 CSV contains no observations")
    return observations


def _parse_boolean(value: str, *, field_name: str, row_number: int) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(
        f"classification {field_name} must be true or false at row {row_number}"
    )


def load_classification(path: Path) -> dict[str, Classification]:
    """Load and validate the exact-label fuel policy seed."""

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CLASSIFICATION_FIELDNAMES:
            raise ValueError(
                "classification seed must have exact header "
                + ",".join(CLASSIFICATION_FIELDNAMES)
            )
        classification: dict[str, Classification] = {}
        for row_number, row in enumerate(reader, start=2):
            label = row["source_fuel_type"]
            if not label:
                raise ValueError(f"classification fuel label is blank at row {row_number}")
            if label in classification:
                raise ValueError(f"duplicate classification fuel label: {label!r}")
            powertrain_group = row["powertrain_group"]
            if powertrain_group not in POWERTRAIN_GROUPS:
                raise ValueError(
                    f"unknown powertrain_group at row {row_number}: {powertrain_group!r}"
                )
            is_bev = _parse_boolean(
                row["is_bev"], field_name="is_bev", row_number=row_number
            )
            is_phev = _parse_boolean(
                row["is_phev"], field_name="is_phev", row_number=row_number
            )
            is_plug_in = _parse_boolean(
                row["is_plug_in_vehicle"],
                field_name="is_plug_in_vehicle",
                row_number=row_number,
            )
            if is_bev and is_phev:
                raise ValueError(f"classification BEV/PHEV overlap at row {row_number}")
            if is_plug_in != (is_bev or is_phev):
                raise ValueError(
                    f"classification plug-in flag is inconsistent at row {row_number}"
                )
            if row["classification_version"] != CLASSIFICATION_VERSION:
                raise ValueError(
                    f"classification_version must be {CLASSIFICATION_VERSION!r}"
                )
            classification[label] = Classification(
                source_fuel_type=label,
                powertrain_group=powertrain_group,
                is_bev=is_bev,
                is_phev=is_phev,
                is_plug_in_vehicle=is_plug_in,
                classification_version=row["classification_version"],
            )
    if not classification:
        raise ValueError("classification seed contains no rows")
    return classification


def _validate_config(config: GenerationConfig) -> list[date]:
    expected_months = _iter_month_ends(
        config.expected_first_month, config.expected_latest_month
    )
    _month_end(
        config.source_catalog_update_month,
        field_name="source catalog update month",
    )
    if not LOWER_SNAKE_CASE.fullmatch(config.source_dataset_id):
        raise ValueError("source_dataset_id must be lower snake case")
    if not config.source_name:
        raise ValueError("source_name is required")
    if not config.source_url:
        raise ValueError("source_url is required")
    return expected_months


def validate(
    observations: Sequence[Observation],
    classification: Mapping[str, Classification],
    config: GenerationConfig,
) -> ValidationSummary:
    """Fail closed on bounds, cadence, categories, labels, and positive totals."""

    if not observations:
        raise ValueError("source contains no observations")
    expected_months = _validate_config(config)
    actual_months = sorted({row.month_end for row in observations})
    if actual_months[0] != expected_months[0]:
        raise ValueError(
            "expected first month "
            f"{expected_months[0].isoformat()}, got {actual_months[0].isoformat()}"
        )
    if actual_months[-1] != expected_months[-1]:
        raise ValueError(
            "expected latest month "
            f"{expected_months[-1].isoformat()}, got {actual_months[-1].isoformat()}"
        )
    if actual_months != expected_months:
        missing = [
            month.isoformat() for month in expected_months if month not in actual_months
        ]
        raise ValueError(f"source does not contain continuous months: missing={missing}")

    for month_end in actual_months:
        categories = {
            row.source_vehicle_category
            for row in observations
            if row.month_end == month_end
        }
        missing_categories = sorted(APPROVED_CATEGORIES - categories)
        unknown_categories = sorted(categories - APPROVED_CATEGORIES)
        if missing_categories or unknown_categories:
            raise ValueError(
                f"{month_end.isoformat()} missing vehicle categories={missing_categories}; "
                f"unknown={unknown_categories}"
            )
        for category in APPROVED_CATEGORIES:
            category_total = sum(
                row.vehicle_population
                for row in observations
                if row.month_end == month_end
                and row.source_vehicle_category == category
            )
            if category_total <= 0:
                raise ValueError(
                    f"{month_end.isoformat()} / {category} category total must be positive"
                )

    observed_fuels = {row.source_fuel_type for row in observations}
    classified_fuels = set(classification)
    unknown_fuels = sorted(observed_fuels - classified_fuels)
    missing_fuels = sorted(classified_fuels - observed_fuels)
    if unknown_fuels or missing_fuels:
        raise ValueError(
            "fuel classification mismatch: "
            f"unknown={unknown_fuels}; missing={missing_fuels}"
        )
    if len(classification) != 9:
        raise ValueError(
            f"initial release classification must contain exactly 9 fuel labels, "
            f"got {len(classification)}"
        )
    latest_month = actual_months[-1]
    latest_totals = {
        category: sum(
            row.vehicle_population
            for row in observations
            if row.month_end == latest_month
            and row.source_vehicle_category == category
        )
        for category in APPROVED_CATEGORIES
    }
    dash_rows = tuple(
        sorted(
            (row for row in observations if row.source_value_status == "source_dash_zero"),
            key=lambda row: (
                row.month_end,
                row.vehicle_type,
                row.source_fuel_type,
            ),
        )
    )
    return ValidationSummary(
        first_month_end=actual_months[0],
        latest_month_end=latest_month,
        month_count=len(actual_months),
        source_vehicle_category_count=len(APPROVED_CATEGORIES),
        source_fuel_type_count=len(observed_fuels),
        latest_month_category_totals=latest_totals,
        dash_rows=dash_rows,
    )


def canonical_release_payload(
    source_dataset_id: str,
    csv_sha256: str,
    latest_month_end: date,
) -> bytes:
    """Build the exact versioned UTF-8 data-identity payload."""

    if not source_dataset_id:
        raise ValueError("source_dataset_id is required")
    if not SHA256_HEX.fullmatch(csv_sha256):
        raise ValueError("csv_sha256 must be 64 lower-case hexadecimal characters")
    return "\x1f".join(
        (
            RELEASE_KEY_VERSION,
            source_dataset_id,
            csv_sha256,
            latest_month_end.isoformat(),
        )
    ).encode("utf-8")


def generate_release_key(
    source_dataset_id: str,
    csv_sha256: str,
    latest_month_end: date,
) -> str:
    """Return the SHA-256 identity for one reviewed source release."""

    return sha256_bytes(
        canonical_release_payload(source_dataset_id, csv_sha256, latest_month_end)
    )


def serialize_csv(
    rows: Iterable[dict[str, Any]], fieldnames: Sequence[str]
) -> bytes:
    """Serialize deterministic UTF-8 CSV with LF line endings."""

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def validate_generated_pair(
    population_rows: Sequence[dict[str, Any]],
    metadata_rows: Sequence[dict[str, Any]],
) -> None:
    """Validate serialized grain, release-key agreement, and metadata reconciliation."""

    if len(metadata_rows) != 1:
        raise ValueError(f"expected one metadata row, got {len(metadata_rows)}")
    if not population_rows:
        raise ValueError("generated observation output contains no rows")
    metadata = metadata_rows[0]
    metadata_key = str(metadata.get("source_release_key", ""))
    population_keys = {
        str(row.get("source_release_key", "")) for row in population_rows
    }
    if population_keys != {metadata_key}:
        raise ValueError(
            "release key mismatch between population and metadata rows: "
            f"population={sorted(population_keys)} metadata={metadata_key!r}"
        )
    if not SHA256_HEX.fullmatch(metadata_key):
        raise ValueError("source_release_key must be 64 lower-case hexadecimal characters")

    grains = [
        (
            str(row.get("month_end", "")),
            str(row.get("source_vehicle_category", "")),
            str(row.get("source_fuel_type", "")),
        )
        for row in population_rows
    ]
    if len(grains) != len(set(grains)):
        raise ValueError("generated observations contain a duplicate source grain")
    if int(metadata.get("source_row_count", -1)) != len(population_rows):
        raise ValueError("metadata source_row_count does not match observations")
    months = sorted({str(row.get("month_end", "")) for row in population_rows})
    if str(metadata.get("first_month_end", "")) != months[0]:
        raise ValueError("metadata first_month_end does not match observations")
    if str(metadata.get("latest_month_end", "")) != months[-1]:
        raise ValueError("metadata latest_month_end does not match observations")
    categories = {
        str(row.get("source_vehicle_category", "")) for row in population_rows
    }
    fuels = {str(row.get("source_fuel_type", "")) for row in population_rows}
    if int(metadata.get("source_vehicle_category_count", -1)) != len(categories):
        raise ValueError("metadata source_vehicle_category_count does not match observations")
    if int(metadata.get("source_fuel_type_count", -1)) != len(fuels):
        raise ValueError("metadata source_fuel_type_count does not match observations")


def build_outputs(
    archive_bytes: bytes,
    classification: Mapping[str, Classification],
    config: GenerationConfig,
    archive_filename: str,
) -> GeneratedOutputs:
    """Parse, validate, serialize, and re-validate both controlled outputs."""

    if not archive_filename:
        raise ValueError("archive_filename is required")
    csv_bytes = parse_archive(archive_bytes)
    observations = parse_rows(csv_bytes)
    summary = validate(observations, classification, config)
    archive_sha256 = sha256_bytes(archive_bytes)
    csv_sha256 = sha256_bytes(csv_bytes)
    release_key = generate_release_key(
        config.source_dataset_id,
        csv_sha256,
        summary.latest_month_end,
    )
    population_rows = [
        {
            "source_release_key": release_key,
            "month_end": row.month_end.isoformat(),
            "source_vehicle_category": row.source_vehicle_category,
            "vehicle_type": row.vehicle_type,
            "source_fuel_type": row.source_fuel_type,
            "source_value_token": row.source_value_token,
            "vehicle_population": row.vehicle_population,
            "source_value_status": row.source_value_status,
        }
        for row in observations
    ]
    population_rows.sort(
        key=lambda row: (
            row["month_end"],
            row["vehicle_type"],
            row["source_fuel_type"],
        )
    )
    metadata_rows = [
        {
            "source_release_key": release_key,
            "source_dataset_id": config.source_dataset_id,
            "source_name": config.source_name,
            "source_url": config.source_url,
            "source_catalog_update_month": config.source_catalog_update_month,
            "source_retrieved_date": config.source_retrieved_date.isoformat(),
            "first_month_end": summary.first_month_end.isoformat(),
            "latest_month_end": summary.latest_month_end.isoformat(),
            "source_row_count": len(population_rows),
            "source_vehicle_category_count": summary.source_vehicle_category_count,
            "source_fuel_type_count": summary.source_fuel_type_count,
            "archive_filename": archive_filename,
            "archive_sha256": archive_sha256,
            "csv_filename": CSV_FILENAME,
            "csv_sha256": csv_sha256,
        }
    ]
    validate_generated_pair(population_rows, metadata_rows)
    population_csv = serialize_csv(population_rows, OBSERVATION_FIELDNAMES)
    metadata_csv = serialize_csv(metadata_rows, RELEASE_FIELDNAMES)

    # Re-validate the exact serialized representation before it can be written.
    validate_generated_pair(
        list(csv.DictReader(io.StringIO(population_csv.decode("utf-8")))),
        list(csv.DictReader(io.StringIO(metadata_csv.decode("utf-8")))),
    )
    return GeneratedOutputs(
        population_csv=population_csv,
        metadata_csv=metadata_csv,
        release_key=release_key,
        archive_sha256=archive_sha256,
        csv_sha256=csv_sha256,
        population_output_sha256=sha256_bytes(population_csv),
        metadata_output_sha256=sha256_bytes(metadata_csv),
        row_count=len(population_rows),
        month_count=summary.month_count,
        source_vehicle_category_count=summary.source_vehicle_category_count,
        source_fuel_type_count=summary.source_fuel_type_count,
        first_month_end=summary.first_month_end,
        latest_month_end=summary.latest_month_end,
        latest_month_category_totals=summary.latest_month_category_totals,
        dash_rows=summary.dash_rows,
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
    """Replace both outputs and roll back a caught partial replacement."""

    if population_path.resolve() == metadata_path.resolve():
        raise ValueError("population and metadata outputs must use different paths")
    if population_path.exists() != metadata_path.exists():
        raise ValueError("population and metadata outputs must both exist or neither exist")

    population_temp: Path | None = None
    metadata_temp: Path | None = None
    population_backup: Path | None = None
    metadata_backup: Path | None = None
    try:
        population_temp = _write_fsynced_temp(population_csv, population_path)
        metadata_temp = _write_fsynced_temp(metadata_csv, metadata_path)
        validate_generated_pair(
            list(csv.DictReader(io.StringIO(population_temp.read_text("utf-8")))),
            list(csv.DictReader(io.StringIO(metadata_temp.read_text("utf-8")))),
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
        elif (
            population_path.exists()
            and population_temp is not None
            and not population_temp.exists()
        ):
            population_path.unlink()
        if metadata_backup is not None:
            os.replace(metadata_backup, metadata_path)
            metadata_backup = None
        elif (
            metadata_path.exists()
            and metadata_temp is not None
            and not metadata_temp.exists()
        ):
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


def print_audit(
    outputs: GeneratedOutputs,
    classification: Mapping[str, Classification],
) -> None:
    """Print the complete deterministic generation audit."""

    print(f"Archive SHA-256: {outputs.archive_sha256}")
    print(f"CSV SHA-256: {outputs.csv_sha256}")
    print(f"Population output SHA-256: {outputs.population_output_sha256}")
    print(f"Metadata output SHA-256: {outputs.metadata_output_sha256}")
    print(f"Source release key: {outputs.release_key}")
    print(f"Observation row count: {outputs.row_count}")
    print(f"Month count: {outputs.month_count}")
    print(f"Vehicle category count: {outputs.source_vehicle_category_count}")
    print(f"Fuel type count: {outputs.source_fuel_type_count}")
    print(
        f"Month bounds: {outputs.first_month_end.isoformat()} "
        f"through {outputs.latest_month_end.isoformat()}"
    )
    for category in sorted(
        outputs.latest_month_category_totals,
        key=lambda value: VEHICLE_TYPE_BY_CATEGORY[value],
    ):
        print(
            f"Latest-month category total: {category} = "
            f"{outputs.latest_month_category_totals[category]}"
        )
    for row in outputs.dash_rows:
        policy = classification[row.source_fuel_type]
        print(
            f"Dash row: {row.month_end.isoformat()} | "
            f"{row.source_vehicle_category} | {row.source_fuel_type} | "
            f"is_bev={str(policy.is_bev).lower()} | "
            f"is_phev={str(policy.is_phev).lower()}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--classification-input", type=Path, required=True)
    parser.add_argument("--retrieved-date", type=date.fromisoformat, required=True)
    parser.add_argument("--catalog-update-month", required=True)
    parser.add_argument("--expected-first-month", required=True)
    parser.add_argument("--expected-latest-month", required=True)
    parser.add_argument("--source-dataset-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.source_dataset_id != APPROVED_SOURCE_DATASET_ID:
        raise ValueError(
            f"source_dataset_id must equal {APPROVED_SOURCE_DATASET_ID!r}"
        )
    classification = load_classification(args.classification_input)
    config = GenerationConfig(
        source_retrieved_date=args.retrieved_date,
        source_catalog_update_month=args.catalog_update_month,
        expected_first_month=args.expected_first_month,
        expected_latest_month=args.expected_latest_month,
        source_dataset_id=args.source_dataset_id,
    )
    outputs = build_outputs(
        args.input.read_bytes(),
        classification,
        config,
        args.input.name,
    )
    write_output_pair(
        outputs.population_csv,
        outputs.metadata_csv,
        args.output,
        args.metadata_output,
    )
    print_audit(outputs, classification)


if __name__ == "__main__":
    main()
