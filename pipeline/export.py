"""Export the dashboard marts from DuckDB to Parquet files for Evidence."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from pipeline import config

log = logging.getLogger(__name__)

# Marts the dashboard reads, with a stable sort so the files are deterministic.
DASHBOARD_TABLES = {
    "fct_monthly_metrics": "year_month",
    "fct_demand_hourly": "year_month, day_of_week, pickup_hour, pickup_borough",
    "fct_daily_congestion": "date_day",
}


def export_dashboard_tables(
    db_path: Path, out_dir: Path = config.DASHBOARD_PARQUET_DIR
) -> dict[str, int]:
    """Write each dashboard mart to out_dir/<table>.parquet; return rows written per table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: dict[str, int] = {}
    with duckdb.connect(str(db_path), read_only=True) as con:
        for table, order_by in DASHBOARD_TABLES.items():
            target = (out_dir / f"{table}.parquet").as_posix().replace("'", "''")
            con.execute(
                f"COPY (SELECT * FROM marts.{table} ORDER BY {order_by}) "
                f"TO '{target}' (FORMAT parquet)"
            )
            rows[table] = con.execute(f"SELECT count(*) FROM marts.{table}").fetchone()[0]
            log.info("Exported %s: %d rows", table, rows[table])
    return rows
