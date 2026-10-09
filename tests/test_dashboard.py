import duckdb
import pytest

from pipeline import dashboard, export


@pytest.fixture(autouse=True)
def no_npm_install(monkeypatch):
    """These tests fake `run_npm`; the install step is covered in test_dashboard_build.py."""
    monkeypatch.setattr(dashboard, "install_dependencies", lambda force: True)


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
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path / "dashboard")
    out_dir = tmp_path / "dashboard" / "parquet" / "real"
    monkeypatch.setattr(dashboard, "run_npm", lambda *args: pytest.fail("npm must not run"))

    assert dashboard.main(["--db", str(marts_db), "--skip-build"]) == 0

    assert sorted(f.name for f in out_dir.iterdir()) == sorted(
        f"{table}.parquet" for table in export.DASHBOARD_TABLES
    )


def test_run_npm_reports_a_missing_npm(monkeypatch, caplog):
    monkeypatch.setattr(dashboard.shutil, "which", lambda name: None)

    assert dashboard.run_npm("ci") is False

    assert "Node.js" in caplog.text


def write_site(site_dir, content="site", pages=dashboard.EXPECTED_PAGES):
    """Write a minimal built site holding the given pages."""
    for page in pages:
        path = dashboard.page_file(site_dir, page)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


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
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path / "dashboard")
    out_dir = tmp_path / "dashboard" / "parquet" / "sample"

    assert dashboard.main(["--sample", "--db", str(db), "--skip-build"]) == 0

    assert sorted(f.name for f in out_dir.iterdir()) == sorted(
        f"{table}.parquet" for table in export.DASHBOARD_TABLES
    )


def test_main_does_not_blame_dbt_for_unrelated_export_errors(marts_db, monkeypatch, caplog):
    def fail(path, out_dir):
        raise duckdb.IOException("disk full")

    monkeypatch.setattr(dashboard.export, "export_dashboard_tables", fail)

    assert dashboard.main(["--db", str(marts_db), "--skip-build"]) == 1

    assert "disk full" in caplog.text
    assert "dbt build" not in caplog.text


def test_sample_and_real_runs_use_separate_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)

    sample, real = dashboard.outputs_for(True), dashboard.outputs_for(False)

    assert sample.parquet_dir != real.parquet_dir
    assert sample.site_dir != real.site_dir
    assert sample.active_dir == real.active_dir  # the pages read one fixed folder


def test_a_sample_run_leaves_the_real_export_and_site_untouched(marts_db, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    real = dashboard.outputs_for(False)
    real.parquet_dir.mkdir(parents=True)
    (real.parquet_dir / "fct_monthly_metrics.parquet").write_text("real data")
    real.site_dir.mkdir(parents=True)
    (real.site_dir / "index.html").write_text("real site")

    def fake_npm(*args):
        write_site(tmp_path / "build", "sample site")
        return True

    monkeypatch.setattr(dashboard, "run_npm", fake_npm)

    assert dashboard.main(["--sample", "--db", str(marts_db)]) == 0

    assert (real.parquet_dir / "fct_monthly_metrics.parquet").read_text() == "real data"
    assert (real.site_dir / "index.html").read_text() == "real site"
    assert (tmp_path / "build" / "index.html").read_text() == "sample site"


def test_a_real_run_moves_its_site_to_build_real_and_clears_stale_pages(
    marts_db, tmp_path, monkeypatch
):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "sample_only.html").write_text("left by a sample run")

    def fake_npm(*args):
        write_site(tmp_path / "build", "real site")
        return True

    monkeypatch.setattr(dashboard, "run_npm", fake_npm)

    assert dashboard.main(["--db", str(marts_db)]) == 0

    assert (tmp_path / "build-real" / "index.html").read_text() == "real site"
    assert not (tmp_path / "build-real" / "sample_only.html").exists()
    assert not (tmp_path / "build").exists()
    active = tmp_path / "parquet" / "active"
    assert sorted(f.name for f in active.iterdir()) == sorted(
        f"{table}.parquet" for table in export.DASHBOARD_TABLES
    )
