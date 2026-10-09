"""The committed dashboard/published-data/ files: aggregates only, and in step with the marts.

They are copied from a real run by `python build_dashboard.py --publish-data` and feed the
public GitHub Pages site, so they must never hold trip-level data and must not drift from
the dbt models.
"""

import json
import subprocess
import sys
from datetime import date

import duckdb
import pytest

from pipeline import config, export

PUBLISHED_DIR = config.DASHBOARD_DIR / "published-data"

# The documented aggregate columns of each mart (docs/metrics.md), in published order.
ALLOWED_COLUMNS = {
    "fct_monthly_metrics": [
        "year_month",
        "month_start",
        "trips",
        "revenue_usd",
        "fare_per_mile_usd",
        "credit_card_trips",
        "tip_rate",
        "is_congestion_pricing_month",
        "cbd_fee_trip_share",
        "manhattan_pickup_trips",
        "manhattan_pickup_avg_fare_usd",
    ],
    "fct_demand_hourly": [
        "year_month",
        "day_of_week",
        "pickup_hour",
        "pickup_borough",
        "trips",
        "revenue_usd",
    ],
    "fct_daily_congestion": [
        "date_day",
        "is_congestion_pricing_active",
        "trips",
        "cbd_fee_trip_share",
        "manhattan_pickup_trips",
        "manhattan_pickup_avg_fare_usd",
    ],
}

# Row-level fields of fct_trips (and raw data); none may appear in a published file.
TRIP_LEVEL_FRAGMENTS = (
    "trip_id",
    "pickup_datetime",
    "dropoff_datetime",
    "pickup_zone",
    "dropoff_zone",
    "location_id",
    "vendor",
    "passenger_count",
    "tip_amount",
    "fare_amount",
    "total_amount",
    "trip_distance",
    "payment_type",
)

# Upper bounds on the grain: a daily mart for a year, an hourly one for 12 months of
# 7 weekdays x 24 hours x 8 boroughs = 16,128 rows at most (the real file has 14,827). The
# hourly cap is kept close to that maximum so a file that grew well past the grain fails here
# instead of relying on the reconciliation tests. Trip rows would be orders of magnitude larger.
MAX_ROWS = {"fct_monthly_metrics": 60, "fct_demand_hourly": 20_000, "fct_daily_congestion": 800}


def published(table):
    return PUBLISHED_DIR / f"{table}.parquet"


def describe(path):
    with duckdb.connect() as con:
        rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [path.as_posix()]).fetchall()
    return [(name, dtype) for name, dtype, *_ in rows]


def scalar(sql, *params):
    with duckdb.connect() as con:
        return con.execute(sql, list(params)).fetchone()[0]


def test_the_published_files_are_exactly_the_dashboard_marts():
    assert sorted(ALLOWED_COLUMNS) == sorted(export.DASHBOARD_TABLES)
    assert sorted(f.name for f in PUBLISHED_DIR.iterdir()) == sorted(
        [f"{table}.parquet" for table in export.DASHBOARD_TABLES] + ["metadata.json"]
    )


@pytest.mark.parametrize("table", list(ALLOWED_COLUMNS))
def test_only_documented_aggregate_columns_are_published(table):
    columns = [name for name, _ in describe(published(table))]

    assert columns == ALLOWED_COLUMNS[table]
    for column in columns:
        assert not any(fragment in column for fragment in TRIP_LEVEL_FRAGMENTS), column


@pytest.mark.parametrize("table", list(ALLOWED_COLUMNS))
def test_published_files_hold_aggregates_not_trips(table):
    rows = scalar("SELECT count(*) FROM read_parquet(?)", published(table).as_posix())

    assert 0 < rows <= MAX_ROWS[table]


def test_published_marts_reconcile_with_each_other():
    monthly = published("fct_monthly_metrics").as_posix()
    hourly = published("fct_demand_hourly").as_posix()
    daily = published("fct_daily_congestion").as_posix()
    with duckdb.connect() as con:
        mismatches = con.execute(
            """
            WITH h AS (SELECT year_month, sum(trips) AS trips FROM read_parquet(?) GROUP BY 1),
            d AS (
                SELECT strftime(date_day, '%Y-%m') AS year_month,
                       sum(trips) AS trips, sum(manhattan_pickup_trips) AS manhattan
                FROM read_parquet(?) GROUP BY 1
            )
            SELECT count(*) FROM read_parquet(?) m
            LEFT JOIN h USING (year_month) LEFT JOIN d USING (year_month)
            WHERE m.trips IS DISTINCT FROM h.trips
               OR m.trips IS DISTINCT FROM d.trips
               OR m.manhattan_pickup_trips IS DISTINCT FROM d.manhattan
            """,
            [hourly, daily, monthly],
        ).fetchone()[0]

    assert mismatches == 0


def test_metadata_describes_the_published_files():
    """The window and date are what a reader uses to judge how fresh the numbers are."""
    metadata = json.loads((PUBLISHED_DIR / "metadata.json").read_text(encoding="utf-8"))
    monthly = published("fct_monthly_metrics").as_posix()
    with duckdb.connect() as con:
        first, last, months, trips = con.execute(
            "SELECT min(year_month), max(year_month), count(*), sum(trips) FROM read_parquet(?)",
            [monthly],
        ).fetchone()

    assert date.fromisoformat(metadata["generated_on"]) <= date.today()
    assert (metadata["first_month"], metadata["last_month"]) == (first, last)
    assert metadata["months"] == months
    assert metadata["valid_trips"] == trips
    for table in export.DASHBOARD_TABLES:
        rows = scalar("SELECT count(*) FROM read_parquet(?)", published(table).as_posix())
        assert metadata["rows"][table] == rows


@pytest.fixture(scope="module")
def sample_marts(tmp_path_factory):
    """A database built by the sample pipeline, i.e. the marts as the models define them now."""
    db = tmp_path_factory.mktemp("marts") / "sample.duckdb"
    result = subprocess.run(
        [sys.executable, "run_pipeline.py", "--sample", "--db", str(db)],
        cwd=config.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return db


@pytest.mark.slow
@pytest.mark.parametrize("table", list(ALLOWED_COLUMNS))
def test_published_schema_matches_the_dbt_marts(sample_marts, table):
    """If a model changes, the published files must be refreshed (see the README)."""
    with duckdb.connect(str(sample_marts), read_only=True) as con:
        rows = con.execute(f"DESCRIBE SELECT * FROM marts.{table}").fetchall()
    in_models = [(name, dtype) for name, dtype, *_ in rows]

    assert describe(published(table)) == in_models, (
        f"{table} changed in the models; refresh with "
        "`python run_pipeline.py` then `python build_dashboard.py --publish-data`"
    )
