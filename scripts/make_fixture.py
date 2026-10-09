"""Regenerate the committed --sample fixture in tests/fixtures/.

For each sample month this takes a systematic sample of the real TLC file
(rows sorted by every column, then every Nth row) and appends handcrafted
edge-case rows that exercise each staging reject rule. The output keeps the
source column names and types, so --sample runs the same loader code path
as real data. Sorting by every column, writing single-threaded and pinning
DuckDB make the output byte-for-byte reproducible.

Usage: python scripts/make_fixture.py [--rows 3000]
Downloads the sample months into data/raw/ first if they are missing.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config, download  # noqa: E402

log = logging.getLogger("make_fixture")

# Each edge case overrides columns of one valid anchor row. The comment on
# each case names the staging rule it must trigger (or "valid").
EDGE_CASES: dict[str, dict[str, str]] = {
    # negative_amount
    "negative_fare": {"fare_amount": "-12.0"},
    # negative_amount
    "negative_total": {"total_amount": "-20.0"},
    # non_positive_duration
    "dropoff_before_pickup": {"tpep_dropoff_datetime": "TIMESTAMP '{month}-15 11:50:00'"},
    # non_positive_duration
    "dropoff_equals_pickup": {"tpep_dropoff_datetime": "TIMESTAMP '{month}-15 12:00:00'"},
    # excessive_duration
    "duration_over_24h": {"tpep_dropoff_datetime": "TIMESTAMP '{month}-16 13:00:00'"},
    # pickup_outside_source_month
    "pickup_previous_month": {
        "tpep_pickup_datetime": "TIMESTAMP '{month}-01 00:00:00' - INTERVAL 1 HOUR",
        "tpep_dropoff_datetime": "TIMESTAMP '{month}-01 00:00:00' + INTERVAL 10 MINUTE",
    },
    # invalid_distance
    "negative_distance": {"trip_distance": "-1.5"},
    # invalid_distance
    "distance_over_100mi": {"trip_distance": "250.0"},
    # unknown_zone
    "unknown_pickup_zone": {"PULocationID": "999"},
    # unknown_zone
    "null_dropoff_zone": {"DOLocationID": "NULL"},
    # valid: zero-distance trips are kept but excluded from fare per mile
    "valid_zero_distance": {"trip_distance": "0.0"},
    # valid: cash trip with a recorded tip, excluded from tip rate
    "valid_cash_with_tip": {"payment_type": "2", "tip_amount": "5.0"},
}

ANCHOR_FILTER = """
    fare_amount > 5 AND total_amount > 10 AND tip_amount > 0
    AND payment_type = 1 AND trip_distance BETWEEN 1 AND 10
    AND PULocationID BETWEEN 1 AND 263 AND DOLocationID BETWEEN 1 AND 263
    AND tpep_dropoff_datetime > tpep_pickup_datetime
    AND strftime(tpep_pickup_datetime, '%Y-%m') = '{month}'
"""


def build_month(con: duckdb.DuckDBPyConnection, src: Path, dest: Path, month: str, rows: int):
    source = f"read_parquet('{src.as_posix()}')"
    columns = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()]
    order_by = ", ".join(f'"{c}" NULLS FIRST' for c in columns)
    total = con.execute(f"SELECT count(*) FROM {source}").fetchone()[0]
    step = max(total // rows, 1)

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE sampled AS
        SELECT * EXCLUDE (rn) FROM (
            SELECT *, row_number() OVER (ORDER BY {order_by}) AS rn FROM {source}
        )
        WHERE rn % {step} = 0
        ORDER BY rn
        LIMIT {rows}
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE anchor AS
        SELECT * REPLACE (
            TIMESTAMP '{month}-15 12:00:00' AS tpep_pickup_datetime,
            TIMESTAMP '{month}-15 12:20:00' AS tpep_dropoff_datetime
        )
        FROM sampled WHERE {ANCHOR_FILTER.format(month=month)}
        ORDER BY {order_by}
        LIMIT 1
        """
    )
    edge_selects = []
    for overrides in EDGE_CASES.values():
        replaces = ", ".join(
            f'CAST({expr.format(month=month)} AS {_type(con, c)}) AS "{c}"'
            for c, expr in overrides.items()
        )
        edge_selects.append(f"SELECT * REPLACE ({replaces}) FROM anchor")

    con.execute(
        f"""
        COPY (
            SELECT * FROM sampled
            UNION ALL BY NAME
            {" UNION ALL BY NAME ".join(edge_selects)}
        ) TO '{dest.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    written = con.execute(f"SELECT count(*) FROM read_parquet('{dest.as_posix()}')").fetchone()[0]
    log.info("%s: %d sampled + %d edge rows -> %s", month, rows, len(EDGE_CASES), dest.name)
    return written


def _type(con: duckdb.DuckDBPyConnection, column: str) -> str:
    return con.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'anchor' AND column_name = ?",
        [column],
    ).fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=3000, help="sampled rows per month")
    parser.add_argument("--out", type=Path, default=config.FIXTURES_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    download.download_trips(config.SAMPLE_MONTHS, config.RAW_DIR)
    download.download_zones(config.RAW_DIR)
    args.out.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads = 1")
    try:
        for month in config.SAMPLE_MONTHS:
            name = config.trip_filename(month)
            build_month(con, config.RAW_DIR / name, args.out / name, month, args.rows)
    finally:
        con.close()
    shutil.copyfile(config.RAW_DIR / config.ZONE_FILENAME, args.out / config.ZONE_FILENAME)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
