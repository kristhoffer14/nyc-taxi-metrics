"""Paths, source URLs and month handling shared by the pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
FIXTURES_DIR = ROOT / "tests" / "fixtures"
DBT_DIR = ROOT / "dbt"
DASHBOARD_DIR = ROOT / "dashboard"
DASHBOARD_PARQUET_DIR = DASHBOARD_DIR / "parquet"

DB_PATH = DATA_DIR / "nyc_taxi.duckdb"
SAMPLE_DB_PATH = DATA_DIR / "sample.duckdb"

TRIP_URL_TEMPLATE = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
)
ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
ZONE_FILENAME = "taxi_zone_lookup.csv"

DEFAULT_START = "2024-07"
DEFAULT_END = "2025-06"
SAMPLE_MONTHS = ("2024-12", "2025-01")

_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True, order=True)
class Month:
    """A calendar month, written as YYYY-MM."""

    year: int
    month: int

    @classmethod
    def parse(cls, text: str) -> Month:
        match = _MONTH_RE.match(text.strip())
        if not match:
            raise ValueError(f"Invalid month {text!r}: expected YYYY-MM")
        year, month = int(match.group(1)), int(match.group(2))
        if not 1 <= month <= 12:
            raise ValueError(f"Invalid month {text!r}: month must be 01-12")
        return cls(year, month)

    def next(self) -> Month:
        if self.month == 12:
            return Month(self.year + 1, 1)
        return Month(self.year, self.month + 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def month_range(start: str, end: str) -> list[str]:
    """Return every month from start to end inclusive, as YYYY-MM strings."""
    first, last = Month.parse(start), Month.parse(end)
    if first > last:
        raise ValueError(f"Start month {first} is after end month {last}")
    months = []
    current = first
    while current <= last:
        months.append(str(current))
        current = current.next()
    return months


def trip_filename(month: str) -> str:
    return f"yellow_tripdata_{Month.parse(month)}.parquet"


def trip_url(month: str) -> str:
    return TRIP_URL_TEMPLATE.format(month=Month.parse(month))
