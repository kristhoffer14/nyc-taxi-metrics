"""Build the static dashboard: export marts to Parquet, then run the Evidence build."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from pipeline import cli, config, export

log = logging.getLogger("pipeline")

EVIDENCE_ERROR_MARKER = "Error in "

# Every page the site must contain; a build missing one of them is a failed build.
EXPECTED_PAGES = ("index", "demand", "fares", "congestion")

# The pages always read `parquet/active/`; each run copies its own export there first.
ACTIVE_PARQUET = "active"

# The published site is served from https://<user>.github.io/<repo>/.
PUBLISHED_BASE_PATH = "/nyc-taxi-metrics"
PUBLISHED_DATA_DIRNAME = "published-data"
METADATA_FILENAME = "metadata.json"
LOCKFILE_STAMP = ".lockfile-hash"


@dataclass(frozen=True)
class Outputs:
    """Where one kind of run (sample or real) keeps its Parquet export and built site."""

    parquet_dir: Path
    site_dir: Path
    active_dir: Path
    scratch_site_dir: Path  # Evidence always writes its site here


def outputs_for(sample: bool) -> Outputs:
    """Sample and real runs never share a folder, so a sample run cannot overwrite real data.

    The sample site stays in `build/` (SPEC section 7 names it); the real site is moved to
    `build-real/` after the build.
    """
    root = config.DASHBOARD_DIR
    scratch = root / "build"
    return Outputs(
        parquet_dir=root / "parquet" / ("sample" if sample else "real"),
        site_dir=scratch if sample else root / "build-real",
        active_dir=root / "parquet" / ACTIVE_PARQUET,
        scratch_site_dir=scratch,
    )


def published_outputs() -> Outputs:
    """Folders for the site built from the committed aggregates (no database needed)."""
    root = config.DASHBOARD_DIR
    return Outputs(
        parquet_dir=root / PUBLISHED_DATA_DIRNAME,
        site_dir=root / "build-published",
        active_dir=root / "parquet" / ACTIVE_PARQUET,
        scratch_site_dir=root / "build",
    )


def write_metadata(published_dir: Path, rows: dict[str, int]) -> dict:
    """Record what the published files cover and when they were generated.

    The schema test cannot see stale values; this file makes the age and window of the data
    visible in review and in the README.
    """
    monthly = (published_dir / "fct_monthly_metrics.parquet").as_posix()
    with duckdb.connect() as con:
        first, last, months, trips = con.execute(
            "SELECT min(year_month), max(year_month), count(*), sum(trips) FROM read_parquet(?)",
            [monthly],
        ).fetchone()
    metadata = {
        "generated_on": date.today().isoformat(),
        "first_month": first,
        "last_month": last,
        "months": months,
        "valid_trips": int(trips),
        "rows": rows,
        "source": "NYC TLC Trip Record Data (yellow taxi), aggregated by this project",
    }
    (published_dir / METADATA_FILENAME).write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return metadata


def stage_parquet(outputs: Outputs) -> None:
    """Replace the folder the pages read with this run's export."""
    shutil.rmtree(outputs.active_dir, ignore_errors=True)
    shutil.copytree(outputs.parquet_dir, outputs.active_dir)


def publish_site(outputs: Outputs) -> None:
    """Move Evidence's site to this run's folder (a no-op for the sample run)."""
    if outputs.site_dir == outputs.scratch_site_dir:
        return
    shutil.rmtree(outputs.site_dir, ignore_errors=True)
    shutil.move(outputs.scratch_site_dir, outputs.site_dir)


def page_file(site_dir: Path, page: str) -> Path:
    return site_dir / "index.html" if page == "index" else site_dir / page / "index.html"


def check_site(site_dir: Path) -> list[str]:
    """Return what is wrong with a built site: missing pages or pages that show an error.

    The `Error in ` scan of the build output depends on Evidence's wording; this check looks
    at the result instead, so a failure that is worded differently still fails the build.
    """
    problems = []
    for page in EXPECTED_PAGES:
        path = page_file(site_dir, page)
        name = path.relative_to(site_dir).as_posix()
        if not path.is_file():
            problems.append(f"missing page: {name}")
        elif EVIDENCE_ERROR_MARKER in path.read_text(encoding="utf-8", errors="replace"):
            problems.append(f"page shows an error: {name}")
    return problems


def lockfile_hash(dashboard_dir: Path) -> str:
    return hashlib.sha256((dashboard_dir / "package-lock.json").read_bytes()).hexdigest()


def needs_install(dashboard_dir: Path, force: bool = False) -> bool:
    """Whether `npm ci` must run: always in CI or when forced, otherwise when the lockfile moved.

    `npm ci` wipes `node_modules`, which is slow. Locally it is skipped when the folder was
    installed from the current `package-lock.json`; CI keeps the clean, lockfile-exact install.
    """
    if force or os.environ.get("CI", "").lower() == "true":
        return True
    stamp = dashboard_dir / "node_modules" / LOCKFILE_STAMP
    if not stamp.is_file():
        return True
    return stamp.read_text(encoding="utf-8").strip() != lockfile_hash(dashboard_dir)


def install_dependencies(force: bool = False) -> bool:
    dashboard_dir = config.DASHBOARD_DIR
    if not needs_install(dashboard_dir, force):
        log.info("node_modules matches package-lock.json; skipping npm ci (--force-install to run)")
        return True
    if not run_npm("ci"):
        return False
    (dashboard_dir / "node_modules" / LOCKFILE_STAMP).write_text(
        lockfile_hash(dashboard_dir), encoding="utf-8"
    )
    return True


@contextmanager
def base_path(path: str | None) -> Iterator[None]:
    """Set Evidence's `deployment.basePath` for one build, then restore the config file."""
    if path is None:
        yield
        return
    config_path = config.DASHBOARD_DIR / "evidence.config.yaml"
    original = config_path.read_bytes()
    text = original.decode("utf-8").rstrip("\n")
    config_path.write_bytes(f"{text}\n\ndeployment:\n  basePath: {path}\n".encode())
    try:
        yield
    finally:
        config_path.write_bytes(original)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build_dashboard.py",
        description="Export the dashboard marts to Parquet and build the static site "
        "into dashboard/build/ (--sample) or dashboard/build-real/.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="build from the sample database (created from the committed fixture if missing)",
    )
    parser.add_argument("--db", type=Path, help="DuckDB file to read (default under data/)")
    parser.add_argument(
        "--published",
        action="store_true",
        help=f"build the site from the committed dashboard/{PUBLISHED_DATA_DIRNAME}/ aggregates "
        "into dashboard/build-published/ with the GitHub Pages base path (no database needed)",
    )
    parser.add_argument(
        "--publish-data",
        action="store_true",
        help=f"export the real-data marts to dashboard/{PUBLISHED_DATA_DIRNAME}/ (to be committed)",
    )
    parser.add_argument(
        "--force-install", action="store_true", help="run npm ci even if node_modules is current"
    )
    parser.add_argument(
        "--skip-build", action="store_true", help="export Parquet only; do not run npm"
    )
    args = parser.parse_args(argv)
    if args.published and (args.sample or args.db or args.publish_data):
        parser.error("--published builds from the committed data; it takes no other data options")
    if args.publish_data and args.sample:
        parser.error("--publish-data exports real data; it cannot be combined with --sample")
    return args


def run_npm(*args: str) -> bool:
    """Run npm in the dashboard directory; return success.

    Evidence exits 0 even when a page query fails (`build:strict` included), so the
    output is scanned for its "Error in ..." messages and counted as a failure.
    """
    npm = shutil.which("npm")
    if npm is None:
        log.error("npm was not found on PATH. Install Node.js 18 or later (https://nodejs.org).")
        return False
    log.info("Running npm %s", " ".join(args))
    process = subprocess.Popen(
        [npm, *args],
        cwd=config.DASHBOARD_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    errors = []
    for line in process.stdout:
        print(line, end="", flush=True)
        if EVIDENCE_ERROR_MARKER in line:
            errors.append(line.strip())
    if errors:
        log.error("Evidence reported %d error(s); first: %s", len(errors), errors[0])
    return process.wait() == 0 and not errors


def build_site(outputs: Outputs, force_install: bool, site_base_path: str | None = None) -> bool:
    """Stage the Parquet files, run Evidence, check the result and move the site."""
    stage_parquet(outputs)
    # Evidence copies into build/ without clearing it, so drop any earlier run's pages first.
    shutil.rmtree(outputs.scratch_site_dir, ignore_errors=True)
    if not install_dependencies(force_install):
        return False
    # `sources` re-reads the Parquet files; `build` alone would reuse a stale cache.
    steps = (("run", "sources:strict"), ("run", "build:strict"))
    with base_path(site_base_path):
        if not all(run_npm(*step) for step in steps):
            return False
    problems = check_site(outputs.scratch_site_dir)
    for problem in problems:
        log.error("Dashboard check failed: %s", problem)
    if problems:
        return False
    publish_site(outputs)
    return True


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    args = parse_args(argv)

    if args.published:
        outputs = published_outputs()
        missing = [
            table
            for table in export.DASHBOARD_TABLES
            if not (outputs.parquet_dir / f"{table}.parquet").is_file()
        ]
        if missing:
            log.error("Missing published data in %s: %s", outputs.parquet_dir, ", ".join(missing))
            return 1
        if args.skip_build:
            return 0
        if not build_site(outputs, args.force_install, PUBLISHED_BASE_PATH):
            log.error("Dashboard build failed")
            return 1
        log.info("Dashboard built: %s", outputs.site_dir)
        return 0

    db_path = args.db or (config.SAMPLE_DB_PATH if args.sample else config.DB_PATH)

    if not db_path.exists():
        if not args.sample:
            log.error("%s not found. Run `python run_pipeline.py` first.", db_path)
            return 1
        log.info("%s not found; running the sample pipeline first", db_path)
        if cli.main(["--sample", "--db", str(db_path)]) != 0:
            return 1

    outputs = outputs_for(args.sample)
    export_dir = config.DASHBOARD_DIR / PUBLISHED_DATA_DIRNAME if args.publish_data else None
    try:
        rows = export.export_dashboard_tables(db_path, export_dir or outputs.parquet_dir)
    except duckdb.CatalogException as exc:
        log.error(
            "The marts are missing from %s (%s). Has `dbt build` been run on it?", db_path, exc
        )
        return 1
    except duckdb.Error as exc:
        log.error("Export from %s failed: %s", db_path, exc)
        return 1

    if export_dir is not None:
        metadata = write_metadata(export_dir, rows)
        log.info("Published data written to %s (%s); commit it", export_dir, metadata)
        return 0
    if args.skip_build:
        return 0
    if not build_site(outputs, args.force_install):
        log.error("Dashboard build failed")
        return 1
    log.info("Dashboard built: %s", outputs.site_dir)
    return 0
