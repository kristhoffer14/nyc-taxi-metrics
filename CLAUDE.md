# nyc-taxi-metrics

DuckDB + dbt analytics engineering project on NYC taxi data. The full spec is in `docs/SPEC.md`; read it at the start of each milestone.

## Commands
- Setup (Windows): `py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt`
- Pipeline on the committed sample: `python run_pipeline.py --sample`
- dbt: `cd dbt; dbt build`
- Checks: `python -m pytest`, `ruff check .`, `ruff format --check .`

## Rules
- All code, comments, docs and commit messages in English.
- Dev machine is Windows 11 with PowerShell; CI is Ubuntu. No bash-only scripts; use pathlib.
- Never read, print or commit `.env` files or credentials. No cloud accounts.
- Work on a branch with small conventional commits; never push to `main`.
- Run lint and tests before every commit.
- After 3 failed attempts at the same problem, stop and write `BLOCKERS.md`.
- Do not edit `docs/SPEC.md`; propose changes in `docs/spec-change-requests.md`.
- Keep `.gitignore` current: never commit data files, build outputs or local settings.