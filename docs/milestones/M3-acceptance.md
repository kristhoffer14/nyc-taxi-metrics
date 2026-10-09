# Milestone 3: acceptance record

Evidence for Milestone 3 (see `docs/SPEC.md`, section 7: "pull request checks are green; README,
decisions and findings are complete"). Recorded on 2026-10-09 on Windows 11, Python 3.12, Node 24.20.0.

## Local run from a fresh clone

A new clone of `feat/m3-ci-docs` (HEAD `8f2b053`) into an empty folder, a new venv, then
`pip install -r requirements-dev.txt`. No `data/` folder existed.

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | 0 | All checks passed |
| `ruff format --check .` | 0 | 35 files already formatted |
| `python -m pytest` | 0 | 82 passed in 89 s |
| `python run_pipeline.py --sample` | 0 | dbt `PASS=65 WARN=0 ERROR=0` |
| `cd dbt; dbt build` | 0 | `PASS=65 WARN=0 ERROR=0` |
| `python build_dashboard.py --sample` | 0 | site built in `dashboard/build/`, all four pages checked |
| `python build_dashboard.py --published` | 0 | site built in `dashboard/build-published/` from the committed aggregates |

The `--published` build reuses Evidence's `build/` folder and moves it to `build-published/`, so
`build/` is gone afterwards; that is expected.

## Checked on the working tree

- The published build puts the base path on every asset and page link (`/nyc-taxi-metrics/_app/...`,
  `/nyc-taxi-metrics/demand`), and `evidence.config.yaml` is restored after the build.
- Screenshots in `docs/img/` come from the real-data build (`dashboard/build-real/`, 12 months).
- `python scripts/compute_findings.py` produced every number quoted in the README findings.
- The TLC page was read: it has no endorsement wording, so none is used (attribution only).
- A real-data rebuild after the lockfile stamp existed skipped `npm ci` (log line "skipping npm ci").

## Not verified yet

- **Green pull request checks on Ubuntu.** The workflows are written and parse as YAML, but they have
  not run on GitHub. The first CI run is also the first Ubuntu run of the dashboard build and of Node 22.
  This row stays open until the run is linked here.
- **The Pages deploy.** It needs Settings -> Pages -> Source: GitHub Actions (set by the owner) and runs
  only on pushes to `main`.
- **Pinned action SHAs** were resolved from the official repositories with `git ls-remote` on
  2026-10-09; each was a tag of that repository, but they have not been run yet.
- **Live site, other time zones, private repositories** (Pages needs a public repository or a paid plan).
