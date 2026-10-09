"""Command-line entry point: download -> load into DuckDB -> dbt build."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb

from pipeline import config, dbt_runner, download, load

log = logging.getLogger("pipeline")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="Download NYC TLC yellow taxi data, load it into DuckDB and run dbt build.",
    )
    parser.add_argument("--start", help=f"first month, YYYY-MM (default {config.DEFAULT_START})")
    parser.add_argument("--end", help=f"last month, YYYY-MM (default {config.DEFAULT_END})")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="use the committed fixture in tests/fixtures/ (no network)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download and reload months that are already present",
    )
    parser.add_argument("--db", type=Path, help="DuckDB file to load (default under data/)")
    parser.add_argument("--skip-dbt", action="store_true", help="load only; do not run dbt")
    parser.add_argument(
        "--show-schema",
        action="store_true",
        help="download the months if needed, print each file's schema and exit "
        "(no database is touched)",
    )
    args = parser.parse_args(argv)
    if args.sample and (args.start or args.end):
        parser.error("--sample cannot be combined with --start/--end")
    try:
        args.months = (
            list(config.SAMPLE_MONTHS)
            if args.sample
            else config.month_range(
                args.start or config.DEFAULT_START, args.end or config.DEFAULT_END
            )
        )
    except ValueError as exc:
        parser.error(str(exc))
    return args


def show_schemas(months: list[str], source_dir: Path) -> int:
    """Print how each month's file differs from the expected schema.

    Returns 1 if any file lacks a required column, so it can gate a milestone.
    """
    schemas = {m: load.describe_trip_file(source_dir / config.trip_filename(m)) for m in months}
    print(f"{'month':<8} {'cols':>4}  missing required | missing optional | unexpected")
    for month, schema in schemas.items():
        print(
            f"{month:<8} {len(schema.columns):>4}  "
            f"{', '.join(schema.missing_required) or '-'} | "
            f"{', '.join(schema.missing_optional) or '-'} | "
            f"{', '.join(schema.unexpected) or '-'}"
        )
    print("\nType differences (file type -> loaded type):")
    differences = {m: s.type_differences for m, s in schemas.items() if s.type_differences}
    for month, diff in differences.items():
        listed = ", ".join(f"{col} {old}->{new}" for col, (old, new) in diff.items())
        print(f"  {month}: {listed}")
    if not differences:
        print("  none")
    return 1 if any(s.missing_required for s in schemas.values()) else 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    args = parse_args(argv)

    if args.sample:
        target, source_dir = "sample", config.FIXTURES_DIR
        db_path = args.db or config.SAMPLE_DB_PATH
        log.info("Sample mode: loading %s from %s", ", ".join(args.months), source_dir)
    else:
        target, source_dir = "dev", config.RAW_DIR
        db_path = args.db or config.DB_PATH
        log.info("Months %s to %s (%d)", args.months[0], args.months[-1], len(args.months))

    try:
        if not args.sample:
            download.download_zones(source_dir, force=args.force)
            download.download_trips(args.months, source_dir, force=args.force)
        if args.show_schema:
            return show_schemas(args.months, source_dir)
        trip_files = {m: source_dir / config.trip_filename(m) for m in args.months}
        results = load.load_all(
            db_path, trip_files, source_dir / config.ZONE_FILENAME, force=args.force
        )
    except (download.DownloadError, load.SchemaError, FileNotFoundError, duckdb.Error) as exc:
        log.error("%s", exc)
        return 1

    for result in results:
        status = "skipped (already loaded)" if result.skipped else "loaded"
        log.info("  %s: %10d rows  %s", result.month, result.rows, status)

    if args.skip_dbt:
        return 0
    if not dbt_runner.run_dbt_build(target, db_path):
        log.error("dbt build failed")
        return 1
    log.info("Pipeline finished: %s", db_path)
    return 0
