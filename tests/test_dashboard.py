import duckdb
import pytest

from pipeline import dashboard, export


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


def test_export_writes_one_parquet_per_mart_with_matching_rows(marts_db, tmp_path):
    out_dir = tmp_path / "parquet"

    rows = export.export_dashboard_tables(marts_db, out_dir)

    assert rows == {"fct_monthly_metrics": 2, "fct_demand_hourly": 2, "fct_daily_congestion": 1}
    for table, expected in rows.items():
        parquet = out_dir / f"{table}.parquet"
        assert duckdb.sql(f"SELECT count(*) FROM '{parquet.as_posix()}'").fetchone()[0] == expected


def test_export_orders_rows_deterministically(marts_db, tmp_path):
    out_dir = tmp_path / "parquet"

    export.export_dashboard_tables(marts_db, out_dir)

    monthly = out_dir / "fct_monthly_metrics.parquet"
    months = duckdb.sql(f"SELECT year_month FROM '{monthly.as_posix()}'").fetchall()
    assert months == [("2024-12",), ("2025-01",)]


def test_main_without_a_database_fails_with_a_hint(tmp_path, caplog):
    missing = tmp_path / "missing.duckdb"

    assert dashboard.main(["--db", str(missing)]) == 1

    assert "run_pipeline.py" in caplog.text
    assert not missing.exists()


def test_main_reports_a_database_without_the_marts(tmp_path, caplog):
    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()

    assert dashboard.main(["--db", str(empty), "--skip-build"]) == 1

    assert "dbt build" in caplog.text


def test_main_skip_build_exports_without_running_npm(marts_db, tmp_path, monkeypatch):
    out_dir = tmp_path / "parquet"
    real_export = export.export_dashboard_tables
    monkeypatch.setattr(
        dashboard.export, "export_dashboard_tables", lambda db: real_export(db, out_dir)
    )
    monkeypatch.setattr(dashboard, "run_npm", lambda *args: pytest.fail("npm must not run"))

    assert dashboard.main(["--db", str(marts_db), "--skip-build"]) == 0

    assert sorted(f.name for f in out_dir.iterdir()) == sorted(
        f"{table}.parquet" for table in export.DASHBOARD_TABLES
    )


def test_run_npm_reports_a_missing_npm(monkeypatch, caplog):
    monkeypatch.setattr(dashboard.shutil, "which", lambda name: None)

    assert dashboard.run_npm("ci") is False

    assert "Node.js" in caplog.text


class FakeProcess:
    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self.returncode = returncode

    def wait(self):
        return self.returncode


@pytest.mark.parametrize(
    ("lines", "returncode", "expected"),
    [
        (["Build complete\n"], 0, True),
        (["Build complete\n"], 1, False),
        (["page | Error in Query! Catalog Error\n", "Build complete\n"], 0, False),
    ],
)
def test_run_npm_fails_on_nonzero_exit_or_evidence_errors(monkeypatch, lines, returncode, expected):
    monkeypatch.setattr(dashboard.shutil, "which", lambda name: "npm")
    monkeypatch.setattr(
        dashboard.subprocess, "Popen", lambda *a, **kw: FakeProcess(lines, returncode)
    )

    assert dashboard.run_npm("run", "build:strict") is expected


def test_main_sample_bootstraps_the_database_then_exports(tmp_path, monkeypatch):
    """Fresh clone: no database exists, so the pipeline runs dbt and the export must still work."""
    db = tmp_path / "sample.duckdb"
    out_dir = tmp_path / "parquet"
    real_export = export.export_dashboard_tables
    monkeypatch.setattr(
        dashboard.export, "export_dashboard_tables", lambda path: real_export(path, out_dir)
    )

    assert dashboard.main(["--sample", "--db", str(db), "--skip-build"]) == 0

    assert sorted(f.name for f in out_dir.iterdir()) == sorted(
        f"{table}.parquet" for table in export.DASHBOARD_TABLES
    )


def test_main_does_not_blame_dbt_for_unrelated_export_errors(marts_db, monkeypatch, caplog):
    def fail(path):
        raise duckdb.IOException("disk full")

    monkeypatch.setattr(dashboard.export, "export_dashboard_tables", fail)

    assert dashboard.main(["--db", str(marts_db), "--skip-build"]) == 1

    assert "disk full" in caplog.text
    assert "dbt build" not in caplog.text
