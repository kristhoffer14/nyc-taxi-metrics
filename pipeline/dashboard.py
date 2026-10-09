"""Build the static dashboard: export marts to Parquet, then run the Evidence build."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

from pipeline import cli, config, export

log = logging.getLogger("pipeline")

EVIDENCE_ERROR_MARKER = "Error in "

# The pages always read `parquet/active/`; each run copies its own export there first.
ACTIVE_PARQUET = "active"


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
        "--skip-build", action="store_true", help="export Parquet only; do not run npm"
    )
    return parser.parse_args(argv)


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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    args = parse_args(argv)
    db_path = args.db or (config.SAMPLE_DB_PATH if args.sample else config.DB_PATH)

    if not db_path.exists():
        if not args.sample:
            log.error("%s not found. Run `python run_pipeline.py` first.", db_path)
            return 1
        log.info("%s not found; running the sample pipeline first", db_path)
        if cli.main(["--sample", "--db", str(db_path)]) != 0:
            return 1

    outputs = outputs_for(args.sample)
    try:
        export.export_dashboard_tables(db_path, outputs.parquet_dir)
    except duckdb.CatalogException as exc:
        log.error(
            "The marts are missing from %s (%s). Has `dbt build` been run on it?", db_path, exc
        )
        return 1
    except duckdb.Error as exc:
        log.error("Export from %s failed: %s", db_path, exc)
        return 1

    if args.skip_build:
        return 0
    stage_parquet(outputs)
    # Evidence copies into build/ without clearing it, so drop any earlier run's pages first.
    shutil.rmtree(outputs.scratch_site_dir, ignore_errors=True)
    # `sources` re-reads the Parquet files; `build` alone would reuse a stale cache.
    steps = (("ci",), ("run", "sources:strict"), ("run", "build:strict"))
    if not all(run_npm(*step) for step in steps):
        log.error("Dashboard build failed")
        return 1
    publish_site(outputs)
    log.info("Dashboard built: %s", outputs.site_dir)
    return 0
