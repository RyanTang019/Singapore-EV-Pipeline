"""Rebuild the deterministic minimal LTA M09 ZIP fixture."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

MEMBER_NAME = "M09-Vehs_by_Fuel_Type.csv"
MONTHS = [
    "2024-01",
    "2024-02",
    "2024-03",
    "2024-04",
    "2024-05",
    "2024-06",
    "2024-07",
    "2024-08",
    "2024-09",
    "2024-10",
    "2024-11",
    "2024-12",
    "2025-01",
]


def build_csv_bytes() -> bytes:
    """Build compact source rows covering every reviewed parser edge."""

    rows: list[tuple[str, str, str, str]] = []
    for index, month in enumerate(MONTHS):
        rows.extend(
            [
                (month, "Cars", "Petrol", str(1_000 + index)),
                (month, "Cars", "Electric", str(100 + index)),
                (month, "Cars", "Petrol-Electric (Plug-In)", str(10 + index)),
                (month, "Taxis", "Diesel", str(200 + index)),
                (month, "Taxis", "Petrol-Electric", str(20 + index)),
                (month, "Motor-cycles", "Petrol", str(300 + index)),
                (month, "Goods & Other Vehicles", "Diesel", str(400 + index)),
                (month, "Goods & Other Vehicles", "Diesel-Electric", str(40 + index)),
                (month, "Goods & Other Vehicles", "Diesel-Electric (Plug-In)", str(1 + index)),
                (month, "Buses", "Diesel", str(50 + index)),
                (month, "Buses", "CNG", str(5 + index)),
                (
                    month,
                    "Buses",
                    "Petrol-CNG",
                    "-" if month == "2024-06" else str(2 + index),
                ),
            ]
        )
        # A published zero is present in one month and the combination is absent in the next.
        if month == "2024-01":
            rows.append((month, "Motor-cycles", "Electric", "0"))

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("month", "category", "type", "number"))
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_zip_bytes() -> bytes:
    """Build byte-identical ZIP bytes with fixed member metadata."""

    buffer = io.BytesIO()
    member = zipfile.ZipInfo(MEMBER_NAME, date_time=(1980, 1, 1, 0, 0, 0))
    member.compress_type = zipfile.ZIP_DEFLATED
    member.create_system = 3
    member.external_attr = 0o100644 << 16
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(member, build_csv_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def main() -> None:
    destination = Path(__file__).with_name("monthly_vehicle_population_by_fuel_minimal.zip")
    destination.write_bytes(build_zip_bytes())


if __name__ == "__main__":
    main()
