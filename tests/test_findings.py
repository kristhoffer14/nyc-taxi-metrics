import subprocess
import sys

from pipeline import config


def test_compute_findings_runs_on_the_published_data():
    result = subprocess.run(
        [sys.executable, "scripts/compute_findings.py"],
        cwd=config.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    assert "Window 2024-07 to 2025-06" in result.stdout
    assert "not causal" in result.stdout
