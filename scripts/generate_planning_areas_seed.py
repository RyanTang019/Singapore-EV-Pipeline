"""Generate ``transform/seeds/planning_areas.csv`` from the URA Master Plan 2019
Planning Area Boundary (No Sea) dataset on data.gov.sg.

One-off, re-runnable build tool — NOT part of the Dagster runtime or the dbt DAG.
It is deterministic: rows are sorted by ``planning_area`` and coordinates are
emitted at a fixed precision, so re-running produces a byte-identical CSV. A
SHA-256 checksum of the output is printed for reproducibility (see spec 3.1).

The dataset exposes clean structured properties (verified 2026-07-10): area/region
come straight from ``PLN_AREA_N`` / ``REGION_N`` — no HTML parsing needed. Geometry
is a mix of ``Polygon`` and ``MultiPolygon`` in lon,lat order (kept as-is for WKT).

Run:  uv run python scripts/generate_planning_areas_seed.py
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import requests
from geomet import wkt

# --- Constants ---------------------------------------------------------------

DATASET_ID = "d_4765db0e87b9c86336792efe8a1f7a66"
POLL_DOWNLOAD_URL = (
    f"https://api-open.data.gov.sg/v1/public/api/datasets/{DATASET_ID}/poll-download"
)

# Repo-relative output path (this file lives in scripts/).
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "transform" / "seeds" / "planning_areas.csv"

EXPECTED_FEATURE_COUNT = 55  # verified against the dataset 2026-07-10
# 7 decimal places of degrees ~= 1.1 cm — far finer than planning-area boundaries
# need, while keeping WKT cells smaller. Fixed value => stable checksum.
COORD_DECIMALS = 7

AREA_FIELD = "PLN_AREA_N"
REGION_FIELD = "REGION_N"
FIELDNAMES = ["planning_area", "region", "boundary_wkt"]

REQUEST_TIMEOUT = 60


# --- Fetch -------------------------------------------------------------------


def fetch_geojson() -> dict:
    """Resolve the signed download URL via the poll-download API, then fetch the GeoJSON."""
    poll = requests.get(POLL_DOWNLOAD_URL, timeout=REQUEST_TIMEOUT)
    poll.raise_for_status()
    payload = poll.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"poll-download failed: {payload.get('errorMsg') or payload}")
    signed_url = payload["data"]["url"]

    resp = requests.get(signed_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# --- Transform ---------------------------------------------------------------


def feature_to_row(feature: dict) -> dict:
    """Extract one seed row (planning_area, region, boundary_wkt) from a GeoJSON feature."""
    props = feature.get("properties") or {}
    planning_area = props.get(AREA_FIELD)
    region = props.get(REGION_FIELD)
    geometry = feature.get("geometry")

    if not planning_area or not region:
        raise ValueError(
            f"feature missing {AREA_FIELD}/{REGION_FIELD}: "
            f"planning_area={planning_area!r}, region={region!r}"
        )
    if not geometry:
        raise ValueError(f"feature {planning_area!r} has no geometry")

    return {
        "planning_area": planning_area.strip().upper(),
        "region": region.strip().upper(),
        "boundary_wkt": wkt.dumps(geometry, decimals=COORD_DECIMALS),
    }


def build_rows(geojson: dict) -> list[dict]:
    """Convert features to validated, deterministically-ordered seed rows."""
    features = geojson.get("features") or []
    if len(features) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_FEATURE_COUNT} features, got {len(features)} — "
            "dataset shape may have changed; re-verify before trusting the seed."
        )

    rows = [feature_to_row(f) for f in features]

    names = [r["planning_area"] for r in rows]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"duplicate planning_area values (must be a unique key): {duplicates}")

    # Deterministic order => byte-identical CSV across runs.
    rows.sort(key=lambda r: r["planning_area"])
    return rows


# --- Write -------------------------------------------------------------------


def write_csv(rows: list[dict], path: Path) -> str:
    """Write rows to `path` (LF line endings) and return the output's SHA-256 hex digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    geojson = fetch_geojson()
    rows = build_rows(geojson)
    checksum = write_csv(rows, OUTPUT_PATH)
    print(f"Wrote {len(rows)} planning areas -> {OUTPUT_PATH}")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    main()
