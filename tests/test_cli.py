import subprocess
import sys

import duckdb
import pytest

from pipeline import cli, config


def test_sample_months_are_fixed():
    assert cli.parse_args(["--sample"]).months == list(config.SAMPLE_MONTHS)


def test_default_window():
    months = cli.parse_args([]).months
    assert (months[0], months[-1]) == (config.DEFAULT_START, config.DEFAULT_END)


@pytest.mark.parametrize(
    "argv",
    [
        ["--sample", "--start", "2025-01"],
        ["--start", "2025-13"],
        ["--start", "2025-02", "--end", "2025-01"],
    ],
)
def test_invalid_arguments_exit_with_usage_error(argv):
    with pytest.raises(SystemExit) as exc:
        cli.parse_args(argv)
    assert exc.value.code == 2


def run_pipeline(*args):
    return subprocess.run(
        [sys.executable, str(config.ROOT / "run_pipeline.py"), *args],
        cwd=config.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


@pytest.mark.slow
def test_sample_pipeline_end_to_end_is_idempotent(tmp_path):
    db = tmp_path / "sample.duckdb"

    first = run_pipeline("--sample", "--db", str(db))
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Completed successfully" in first.stdout

    second = run_pipeline("--sample", "--db", str(db))
    assert second.returncode == 0, second.stdout + second.stderr
    assert second.stdout.count("skipped (already loaded)") == len(config.SAMPLE_MONTHS)

    with duckdb.connect(str(db), read_only=True) as con:

        def count(table):
            return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

        raw = count("raw.yellow_trips")
        valid = count("marts.fct_trips")
        rejected = count("staging.stg_yellow_trips_rejected")
        months = count("marts.fct_monthly_metrics")
    assert raw == 2 * 3012
    assert valid + rejected == raw
    assert months == 2


def test_download_failure_logs_clear_error_and_returns_nonzero(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise cli.download.DownloadError("Giving up on http://x after 4 attempts: reset")

    monkeypatch.setattr(cli.download, "download_zones", fail)
    assert cli.main(["--start", "2024-12", "--end", "2024-12"]) == 1
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert [r.getMessage() for r in errors] == ["Giving up on http://x after 4 attempts: reset"]
    assert all(r.exc_info is None for r in errors)


def test_show_schema_prints_every_month_and_touches_no_database(capsys, tmp_path):
    db = tmp_path / "never.duckdb"
    assert cli.main(["--sample", "--show-schema", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "2024-12" in out and "2025-01" in out
    assert "cbd_congestion_fee" in out  # reported as missing for 2024-12
    assert not db.exists()
