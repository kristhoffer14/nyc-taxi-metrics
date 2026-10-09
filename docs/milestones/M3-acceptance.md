# Milestone 3: acceptance record

Evidence for Milestone 3 (see `docs/SPEC.md`, section 7: "pull request checks are green; README,
decisions and findings are complete"). Recorded on 2026-10-09 on Windows 11, Python 3.12, Node 24.20.0.

## Local run from a fresh clone

A new clone of `feat/m3-ci-docs` (HEAD `8f2b053`, the commit this run was made on) into an empty
folder, a new venv, then `pip install -r requirements-dev.txt`. No `data/` folder existed. This run
was not repeated on later commits; the same commands ran in CI on `0e5ba66` (next section).

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

## Pull request checks on GitHub

Pull request #3, head `0e5ba66`. Run: <https://github.com/kristhoffer14/nyc-taxi-metrics/actions/runs/37989118483>

| Job | Conclusion |
|---|---|
| Lint, tests, sample pipeline, dbt (`ruff`, `pytest`, `run_pipeline.py --sample`, `dbt build`) | success |
| Dashboard build (sample), including the `--published` build and the page checks | success |

This is the first run on Ubuntu 24.04 and on Node 22. An earlier run on `17d9035`
(<https://github.com/kristhoffer14/nyc-taxi-metrics/actions/runs/37986173295>) also succeeded.

## Checked on the working tree

- The published build puts the base path on every asset and page link (`/nyc-taxi-metrics/_app/...`,
  `/nyc-taxi-metrics/demand`), and `evidence.config.yaml` is restored after the build.
- Screenshots in `docs/img/` come from the real-data build (`dashboard/build-real/`, 12 months).
- `python scripts/compute_findings.py` produced every number quoted in the README findings except
  the rejected-trip counts, which come from `M2-acceptance.md`; `tests/test_findings.py` now checks
  the quoted figures against the script.
- The TLC page was read: it has no endorsement wording, so none is used (attribution only).
- A real-data rebuild after the lockfile stamp existed skipped `npm ci` (log line "skipping npm ci").

## Not verified yet

- **The Pages deploy.** The owner reports the Pages source is now set to GitHub Actions; this record
  did not check it. `pages.yml` has not run: it runs only on pushes to `main`, so the first deploy
  is after the merge. `actions/configure-pages` was removed because its outputs are not used (the
  base path is fixed in `pipeline/dashboard.py`), so the build job needs no `pages` permission.
- **Two pinned action SHAs have not run.** `upload-pages-artifact` and `deploy-pages` run only in
  `pages.yml`. `checkout`, `setup-python` and `setup-node` ran in CI. All five SHAs in use were
  resolved to their tags from the official repositories with `git ls-remote` on 2026-10-09.
- **Live site, other time zones, private repositories** (Pages needs a public repository or a paid
  plan). The README link returns 404 until the first deploy.
