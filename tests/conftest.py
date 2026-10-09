"""Shared fixtures."""

import duckdb
import pytest


@pytest.fixture
def marts_db(tmp_path):
    """A database with the three dashboard marts, each holding a few rows."""
    db = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.fct_monthly_metrics AS "
            "SELECT * FROM (VALUES ('2025-01', 10), ('2024-12', 7)) t(year_month, trips)"
        )
        con.execute(
            "CREATE TABLE marts.fct_demand_hourly AS "
            "SELECT * FROM (VALUES ('2025-01', 2, 9, 'Queens', 3), ('2025-01', 1, 8, 'Bronx', 4)) "
            "t(year_month, day_of_week, pickup_hour, pickup_borough, trips)"
        )
        con.execute(
            "CREATE TABLE marts.fct_daily_congestion AS "
            "SELECT * FROM (VALUES (DATE '2025-01-05', 5)) t(date_day, trips)"
        )
    return db
