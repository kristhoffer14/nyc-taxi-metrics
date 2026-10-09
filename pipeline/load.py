"""Load downloaded files into the raw schema of a DuckDB database.

The raw layer keeps source values as delivered, with three changes:
columns are matched by name case-insensitively (the files change casing,
e.g. ``Airport_fee``), every column is cast to one fixed type, and
optional columns missing from a file (``cbd_congestion_fee`` before 2025)
are filled with NULL. Each row also records the month and file it came
from and its 1-based position in that file: staging needs the month to
reject pickups outside it, and month plus position is the trip key.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import duckdb

from pipeline import config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawColumn:
    name: str
    type: str
    required: bool


# Raw column names are the source names lower-cased. Staging renames them.
TRIP_COLUMNS: tuple[RawColumn, ...] = (
    RawColumn("vendorid", "INTEGER", True),
    RawColumn("tpep_pickup_datetime", "TIMESTAMP", True),
    RawColumn("tpep_dropoff_datetime", "TIMESTAMP", True),
    RawColumn("passenger_count", "BIGINT", False),
    RawColumn("trip_distance", "DOUBLE", True),
    RawColumn("ratecodeid", "BIGINT", False),
    RawColumn("store_and_fwd_flag", "VARCHAR", False),
    RawColumn("pulocationid", "INTEGER", True),
    RawColumn("dolocationid", "INTEGER", True),
    RawColumn("payment_type", "BIGINT", True),
    RawColumn("fare_amount", "DOUBLE", True),
    RawColumn("extra", "DOUBLE", False),
    RawColumn("mta_tax", "DOUBLE", False),
    RawColumn("tip_amount", "DOUBLE", True),
    RawColumn("tolls_amount", "DOUBLE", False),
    RawColumn("improvement_surcharge", "DOUBLE", False),
    RawColumn("total_amount", "DOUBLE", True),
    RawColumn("congestion_surcharge", "DOUBLE", False),
    RawColumn("airport_fee", "DOUBLE", False),
    RawColumn("cbd_congestion_fee", "DOUBLE", False),
)

ZONE_COLUMNS = {
    "LocationID": "INTEGER",
    "Borough": "VARCHAR",
    "Zone": "VARCHAR",
    "service_zone": "VARCHAR",
}


class SchemaError(ValueError):
    """Raised when a source file lacks a required column."""


@dataclass(frozen=True)
class LoadResult:
    month: str
    rows: int
    skipped: bool


@contextmanager
def connect(db_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the database, create the raw schema, and always close it.

    Closing matters on Windows: dbt cannot open the file while this
    process holds it.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        _create_raw_schema(con)
        yield con
    finally:
        con.close()


def _create_raw_schema(con: duckdb.DuckDBPyConnection) -> None:
    columns = ",\n    ".join(f"{c.name} {c.type}" for c in TRIP_COLUMNS)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS raw.yellow_trips (
            {columns},
            source_month VARCHAR NOT NULL,
            source_file VARCHAR NOT NULL,
            source_row BIGINT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.load_log (
            source_month VARCHAR PRIMARY KEY,
            source_file VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            loaded_at TIMESTAMP NOT NULL
        )
        """
    )


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _trip_select_list(source_columns: list[str], path: Path) -> str:
    by_lower = {name.lower(): name for name in source_columns}
    missing = [c.name for c in TRIP_COLUMNS if c.required and c.name not in by_lower]
    if missing:
        raise SchemaError(f"{path.name} is missing required columns: {', '.join(missing)}")
    parts = []
    for column in TRIP_COLUMNS:
        source = by_lower.get(column.name)
        expr = f'"{source}"' if source else "NULL"
        parts.append(f"CAST({expr} AS {column.type}) AS {column.name}")
    return ",\n    ".join(parts)


def is_loaded(con: duckdb.DuckDBPyConnection, month: str) -> bool:
    row = con.execute("SELECT 1 FROM raw.load_log WHERE source_month = ?", [month]).fetchone()
    return row is not None


def load_trip_month(
    con: duckdb.DuckDBPyConnection, month: str, path: Path, *, force: bool = False
) -> LoadResult:
    """Load one month idempotently: skip if logged, else replace its rows."""
    month = str(config.Month.parse(month))
    if is_loaded(con, month) and not force:
        rows = con.execute(
            "SELECT row_count FROM raw.load_log WHERE source_month = ?", [month]
        ).fetchone()[0]
        log.info("Month %s already loaded (%d rows); skipping", month, rows)
        return LoadResult(month, rows, skipped=True)

    if not path.exists():
        raise FileNotFoundError(f"Trip file for {month} not found: {path}")
    source = f"read_parquet({_sql_string(path.as_posix())})"
    source_columns = [row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()]
    select_list = _trip_select_list(source_columns, path)

    con.execute("BEGIN TRANSACTION")
    try:
        con.execute("DELETE FROM raw.yellow_trips WHERE source_month = ?", [month])
        con.execute(
            f"""
            INSERT INTO raw.yellow_trips
            SELECT {select_list}, ? AS source_month, ? AS source_file,
                file_row_number + 1 AS source_row
            FROM read_parquet({_sql_string(path.as_posix())}, file_row_number = true)
            """,
            [month, path.name],
        )
        rows = con.execute(
            "SELECT count(*) FROM raw.yellow_trips WHERE source_month = ?", [month]
        ).fetchone()[0]
        con.execute("DELETE FROM raw.load_log WHERE source_month = ?", [month])
        con.execute(
            "INSERT INTO raw.load_log VALUES (?, ?, ?, current_timestamp::TIMESTAMP)",
            [month, path.name, rows],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    log.info("Loaded month %s: %d rows from %s", month, rows, path.name)
    return LoadResult(month, rows, skipped=False)


def load_zones(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    """Replace raw.taxi_zones from the lookup CSV (small, so always reloaded)."""
    if not path.exists():
        raise FileNotFoundError(f"Zone lookup not found: {path}")
    columns = "{" + ", ".join(f"'{k}': '{v}'" for k, v in ZONE_COLUMNS.items()) + "}"
    con.execute(
        f"""
        CREATE OR REPLACE TABLE raw.taxi_zones AS
        SELECT * FROM read_csv({_sql_string(path.as_posix())}, header = true, columns = {columns})
        """
    )
    rows = con.execute("SELECT count(*) FROM raw.taxi_zones").fetchone()[0]
    log.info("Loaded zone lookup: %d rows", rows)
    return rows


def load_all(
    db_path: Path, trip_files: Mapping[str, Path], zone_path: Path, *, force: bool = False
) -> list[LoadResult]:
    """Load the zone lookup and every month, then close the database."""
    with connect(db_path) as con:
        load_zones(con, zone_path)
        return [
            load_trip_month(con, month, path, force=force)
            for month, path in sorted(trip_files.items())
        ]
