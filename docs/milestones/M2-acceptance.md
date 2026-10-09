# Milestone 2: acceptance record

Evidence for Milestone 2 (see `docs/SPEC.md`, section 7). Recorded on 2026-10-09 on Windows 11,
Python 3.12, Node 24.20.0, from the committed sample fixture (months 2024-12 and 2025-01).

| # | Criterion | Result |
|---|---|---|
| 1 | Spec commit first on `feat/m2-dashboard`; diff touches only the SCR changes | Met. `git diff main --stat -- docs/SPEC.md`: 8 insertions, 2 deletions (SCR-1 to SCR-4 only) |
| 2 | `python build_dashboard.py --sample` exits 0 and creates `dashboard/build/index.html` | Met. Exit 0; `index.html`, `demand/`, `fares/` and `congestion/` pages exist |
| 3 | Three pages with data window and caveats | Met on screenshots of the served build (headless Edge) |
| 4 | Congestion page: "descriptive, not causal", n/a before 2025-01, marker at 2025-01-05 | Met. Notice shown; table reads n/a for 2024-12; dashed marker labelled 2025-01-05 |
| 5 | `cd dbt && dbt build` exits 0 with all tests passing | Met. `PASS=65 WARN=0 ERROR=0` (49 data tests, 6 unit tests) |
| 6 | Page totals equal the marts | Met. Per month, `fct_monthly_metrics`, `fct_demand_hourly` and `fct_daily_congestion` all give 2,945 (2024-12) and 2,869 (2025-01); home page total 5,814 |
| 7 | New mart columns documented in `docs/metrics.md` | Met. "Dashboard marts" section |
| 8 | `pytest`, `ruff check`, `ruff format --check` clean; nothing generated tracked | Met. 49 passed; ruff clean; `git status` clean after commits |
| 9 | Tool choice recorded in `docs/decisions.md` | Met |

## Not verified

- **Ubuntu build.** Only Windows was run. The Ubuntu check belongs to the M3 CI workflow.
- **Real data.** The dashboard was built only from the sample. A build with `--db data/nyc_taxi.duckdb`
  has not been run, and the sample has two months, so the trend charts have two points.
- **Reference line position.** Evidence formats the 2025-01-05 marker from a UTC date; its position
  can be offset by hours depending on the viewer's time zone. The label text is fixed.
