"""Site checks, the npm install shortcut, the Pages base path and the published-data mode."""

import json
from datetime import date

import pytest

from pipeline import dashboard, export


def write_site(site_dir, content="site", pages=dashboard.EXPECTED_PAGES):
    for page in pages:
        path = dashboard.page_file(site_dir, page)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_check_site_accepts_a_complete_site(tmp_path):
    write_site(tmp_path)

    assert dashboard.check_site(tmp_path) == []


def test_check_site_reports_a_missing_page(tmp_path):
    write_site(tmp_path, pages=("index", "demand", "fares"))

    assert dashboard.check_site(tmp_path) == ["missing page: congestion/index.html"]


def test_check_site_reports_a_page_that_shows_an_error(tmp_path):
    write_site(tmp_path)
    dashboard.page_file(tmp_path, "fares").write_text("<p>Error in Query: boom</p>")

    assert dashboard.check_site(tmp_path) == ["page shows an error: fares/index.html"]


def test_a_build_missing_a_page_fails_and_publishes_nothing(marts_db, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    monkeypatch.setattr(dashboard, "install_dependencies", lambda force: True)

    def fake_npm(*args):
        write_site(tmp_path / "build", pages=("index",))
        return True

    monkeypatch.setattr(dashboard, "run_npm", fake_npm)

    assert dashboard.main(["--db", str(marts_db)]) == 1
    assert not (tmp_path / "build-real").exists()


def _lockfile(dashboard_dir, text="{}"):
    (dashboard_dir / "package-lock.json").write_text(text)
    (dashboard_dir / "node_modules").mkdir(exist_ok=True)


def test_needs_install_without_a_stamp(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    _lockfile(tmp_path)

    assert dashboard.needs_install(tmp_path) is True


def test_install_is_skipped_when_the_lockfile_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    _lockfile(tmp_path)
    calls = []
    monkeypatch.setattr(dashboard, "run_npm", lambda *a: calls.append(a) or True)

    assert dashboard.install_dependencies() is True  # first run installs and stamps
    assert dashboard.install_dependencies() is True  # second run skips

    assert calls == [("ci",)]
    assert dashboard.needs_install(tmp_path) is False


def test_install_runs_again_when_the_lockfile_changes_or_is_forced(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    _lockfile(tmp_path)
    monkeypatch.setattr(dashboard, "run_npm", lambda *a: True)
    dashboard.install_dependencies()

    (tmp_path / "package-lock.json").write_text('{"changed": true}')
    assert dashboard.needs_install(tmp_path) is True

    dashboard.install_dependencies()
    assert dashboard.needs_install(tmp_path) is False
    assert dashboard.needs_install(tmp_path, force=True) is True


def test_install_always_runs_in_ci(tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    _lockfile(tmp_path)
    stamp = tmp_path / "node_modules" / dashboard.LOCKFILE_STAMP
    stamp.write_text(dashboard.lockfile_hash(tmp_path))

    assert dashboard.needs_install(tmp_path) is True


def test_a_failed_install_stops_the_build(marts_db, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    monkeypatch.setattr(dashboard, "install_dependencies", lambda force: False)
    monkeypatch.setattr(dashboard, "run_npm", lambda *a: pytest.fail("npm must not run"))

    assert dashboard.main(["--db", str(marts_db)]) == 1


def test_base_path_is_set_for_the_build_and_restored_after(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    config_file = tmp_path / "evidence.config.yaml"
    config_file.write_bytes(b"appearance:\n  default: system\n")

    with dashboard.base_path("/repo"):
        text = config_file.read_text()
        assert "deployment:\n  basePath: /repo" in text
        assert text.startswith("appearance:")

    assert config_file.read_bytes() == b"appearance:\n  default: system\n"


def test_base_path_is_restored_when_the_build_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    config_file = tmp_path / "evidence.config.yaml"
    config_file.write_bytes(b"a: 1\n")

    with pytest.raises(RuntimeError), dashboard.base_path("/repo"):
        raise RuntimeError("build failed")

    assert config_file.read_bytes() == b"a: 1\n"


def test_published_build_uses_the_committed_data_and_the_pages_base_path(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    monkeypatch.setattr(dashboard, "install_dependencies", lambda force: True)
    (tmp_path / "evidence.config.yaml").write_text("a: 1\n")
    data = tmp_path / dashboard.PUBLISHED_DATA_DIRNAME
    data.mkdir()
    for table in export.DASHBOARD_TABLES:
        (data / f"{table}.parquet").write_text("published")
    seen = {}

    def fake_npm(*args):
        seen["config"] = (tmp_path / "evidence.config.yaml").read_text()
        write_site(tmp_path / "build", "published site")
        return True

    monkeypatch.setattr(dashboard, "run_npm", fake_npm)

    assert dashboard.main(["--published"]) == 0

    assert f"basePath: {dashboard.PUBLISHED_BASE_PATH}" in seen["config"]
    assert (tmp_path / "build-published" / "index.html").read_text() == "published site"
    assert (tmp_path / "evidence.config.yaml").read_text() == "a: 1\n"
    assert (data / "fct_monthly_metrics.parquet").read_text() == "published"


def test_published_build_without_data_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)

    assert dashboard.main(["--published"]) == 1

    assert "Missing published data" in caplog.text


def test_publish_data_exports_the_marts_to_the_committed_folder(marts_db, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.config, "DASHBOARD_DIR", tmp_path)
    monkeypatch.setattr(dashboard, "run_npm", lambda *a: pytest.fail("npm must not run"))

    assert dashboard.main(["--db", str(marts_db), "--publish-data"]) == 0

    published = tmp_path / dashboard.PUBLISHED_DATA_DIRNAME
    assert sorted(f.name for f in published.iterdir()) == sorted(
        [f"{table}.parquet" for table in export.DASHBOARD_TABLES] + [dashboard.METADATA_FILENAME]
    )
    metadata = json.loads((published / dashboard.METADATA_FILENAME).read_text())
    assert metadata["generated_on"] == date.today().isoformat()
    assert metadata["first_month"] == "2024-12"
    assert metadata["last_month"] == "2025-01"
    assert metadata["valid_trips"] == 17
    assert metadata["rows"]["fct_monthly_metrics"] == 2


def test_publish_data_cannot_use_the_sample_database():
    with pytest.raises(SystemExit):
        dashboard.parse_args(["--publish-data", "--sample"])
