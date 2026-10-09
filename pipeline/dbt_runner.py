"""Run dbt in a child process against the DuckDB file the pipeline just loaded."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from pipeline import config

log = logging.getLogger(__name__)

# Environment variables read by dbt/profiles.yml, one per target.
DB_ENV_VAR = {"sample": "NYC_TAXI_SAMPLE_DB", "dev": "NYC_TAXI_DB"}


def run_dbt_build(target: str, db_path: Path, project_dir: Path = config.DBT_DIR) -> bool:
    """Run `dbt build` for target with its database at db_path; return success.

    dbt runs in a child process: in-process, its adapter keeps a read-write connection to
    the DuckDB file open after the build, which blocks later read-only connections.
    """
    env = {**os.environ, DB_ENV_VAR[target]: str(db_path.resolve())}
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
    command = [sys.executable, "-c", "from dbt.cli.main import cli; cli()", *args]
    return subprocess.run(command, env=env, check=False).returncode == 0
