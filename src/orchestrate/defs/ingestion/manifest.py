"""Declarative source manifest: one SourceConfig per source, plus the shared retry policy and
default cron. Adding an OData source is a one-line entry here — no new asset/fetch module.

Decisions (spec 2026-06-12, resolved 2026-06-14): Python (not YAML); all three default to a
30-min cron with a per-source override; EV moves from hourly to 30 min deliberately.
"""

from dataclasses import dataclass

from dagster import Backoff, RetryPolicy

from .extractors import Extractor, ODataPagedExtractor, S3LinkExtractor

EVCBATCH_URL = "https://datamall2.mytransport.sg/ltaodataservice/EVCBatch"
TRAFFIC_SPEED_BANDS_URL = (
    "https://datamall2.mytransport.sg/ltaodataservice/v3/TrafficSpeedBands"
)
CARPARK_AVAILABILITY_URL = (
    "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2"
)

# Shared in-run retry: ride out a transient DNS/connection blip on a scheduled tick. Dagster
# does not back-fill missed cron boundaries, so in-run retry is the only per-tick safety net.
STANDARD_RETRY = RetryPolicy(max_retries=3, delay=10, backoff=Backoff.EXPONENTIAL)

# Every 30 min (SGT). Overridable per source via SourceConfig.cron — the escape hatch if the
# 4 GB VM's QueuedRunCoordinator ever bunches up under serial runs.
DEFAULT_CRON = "*/30 * * * *"


@dataclass(frozen=True)
class SourceConfig:
    name: str  # source_name AND raw table name AND dagster asset name
    extractor: Extractor  # how to fetch
    records_key: str  # top-level key of the records array (count metadata + dbt parity)
    cron: str = DEFAULT_CRON  # schedule cadence; edit per source if needed


MANIFEST = [
    SourceConfig(
        "ev_charger_availability", S3LinkExtractor(EVCBATCH_URL), "evLocationsData"
    ),
    SourceConfig(
        "traffic_speed_bands",
        ODataPagedExtractor(TRAFFIC_SPEED_BANDS_URL),
        "value",
    ),
    SourceConfig(
        "carpark_availability",
        ODataPagedExtractor(CARPARK_AVAILABILITY_URL),
        "value",
    ),
]
