"""Run dbt in-process against the DuckDB file the pipeline just loaded."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pipeline import config

log = logging.getLogger(__name__)

# Environment variables read by dbt/profiles.yml, one per target.
DB_ENV_VAR = {"sample": "NYC_TAXI_SAMPLE_DB", "dev": "NYC_TAXI_DB"}


def run_dbt_build(target: str, db_path: Path, project_dir: Path = config.DBT_DIR) -> bool:
    """Run `dbt build` for target with its database at db_path; return success."""
    # Imported lazily: dbt is slow to import and not needed by the loader tests.
    from dbt.cli.main import dbtRunner

    os.environ[DB_ENV_VAR[target]] = str(db_path.resolve())
    args = [
        "build",
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir),
        "--target",
        target,
    ]
    log.info("Running dbt %s", " ".join(args))
    result = dbtRunner().invoke(args)
    if result.exception is not None:
        log.error("dbt build raised: %s", result.exception)
    return bool(result.success)
