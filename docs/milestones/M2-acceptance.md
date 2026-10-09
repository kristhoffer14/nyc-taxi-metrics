# Milestone 2: acceptance record

Evidence for Milestone 2 (see `docs/SPEC.md`, section 7). Recorded on 2026-10-09 on Windows 11,
Python 3.12, Node 24.20.0, from the committed sample fixture (months 2024-12 and 2025-01).

**Re-run after review.** The first record (commit `01aa362`) was made in a working tree that already
had `data/`, so the bootstrap path was never exercised. A review found `python build_dashboard.py
--sample` failed on a fresh clone. After the fixes, every criterion below was re-run in a **new
clone of `feat/m2-dashboard` (HEAD `303d8c1`) with a new venv** and no `data/` folder. The venv
and `pip install -r requirements-dev.txt` come first; `python build_dashboard.py --sample` was the
first project command run. Node was added to `PATH` for the shell; nothing else was prepared.

| # | Criterion | Result |
|---|---|---|
| 1 | Spec commit first on `feat/m2-dashboard`; diff touches only the SCR changes | Met. First commit is `8848305 docs(spec): incorporate SCR-1 to SCR-4`; `git diff origin/main --stat -- docs/SPEC.md`: 8 insertions, 2 deletions |
| 2 | `python build_dashboard.py --sample` exits 0 and creates `dashboard/build/index.html` | Met, from a clone with no `data/`. Exit 0 in 148 s: sample pipeline (dbt `PASS=65`), export (2, 688 and 62 rows), `npm ci`, `sources:strict`, `build:strict`. `index.html`, `demand/`, `fares/` and `congestion/` exist; the sample Parquet is in `dashboard/parquet/sample/` |
| 3 | Three pages with data window and caveats | Met. Headless Edge screenshots and DOM dumps of the served build: each page shows "Data window" (2024-12 to 2025-01) and no `Error in` text. Pages have caveat sections |
| 4 | Congestion page: "descriptive, not causal", n/a before 2025-01, marker at 2025-01-05 | Met. Warning shown; table reads n/a for 2024-12 and 66.7% for 2025-01; dashed marker labelled "Tolling starts 2025-01-05" on all three daily charts. The note about the four pre-toll days of January now sits under the before/after table |
| 5 | `cd dbt && dbt build` exits 0 with all tests passing | Met. Exit 0, `PASS=65 WARN=0 ERROR=0` (49 data tests, 6 unit tests) |
| 6 | Page totals equal the marts | Met. `fct_monthly_metrics`, `fct_demand_hourly` and `fct_daily_congestion` each give 2,945 (2024-12) and 2,869 (2025-01), total 5,814; the home page shows 5,814 |
| 7 | New mart columns documented in `docs/metrics.md` | Met. "Dashboard marts" section |
| 8 | `pytest`, `ruff check`, `ruff format --check` clean; nothing generated tracked | Met. 54 passed; ruff clean; `git status` clean; tracked files matching `parquet` are only the two committed fixtures |
| 9 | Tool choice recorded in `docs/decisions.md` | Met |

**Hour axis.** The earlier note said `xMax=23` "is ignored by Evidence" and marked the page as met. The
cause was not the value or its type: Evidence's `LineChart` has no `xMin`/`xMax` props at all (only
`yMin`/`yMax`), so passing `xMin={0} xMax={23}` as numbers also changes nothing (checked: the axis
still ended at 25). The hour charts now plot a zero-padded hour on a category axis and end at `23`,
confirmed on screenshots of both the real-data and the sample builds. The earlier "Met" for criterion
3 was therefore too generous; it is met only with this change.

Visible limits seen in the re-run screenshots, not fixed here:
- On the 2-month sample the borough charts label their axis `0M`/`$0M` (values are far below a
  million), and the daily congestion charts show truncated x labels (`2 2 2 ...`) because 62 dates
  do not fit. Label legibility of those daily charts was not checked on the real-data build.

## Full window, real data (2024-07 to 2025-06)

Run on 2026-10-09 against `data/nyc_taxi.duckdb` after `python run_pipeline.py` loaded all 12 months
(the raw files were already in `data/raw/`; no download was needed).

| Check | Result |
|---|---|
| Free disk before load | 219 GB; database ended at 2.68 GB (estimate was about 4 GB) |
| Raw rows loaded | 44,921,011 |
| Valid trips (`fct_trips`) | 42,971,314 |
| Rejected trips | 1,949,697 (valid + rejected = raw) |
| `dbt build` (dev target) | `PASS=65 WARN=0 ERROR=0`, 265 s |
| Parquet exported | `fct_monthly_metrics` 12 rows, `fct_demand_hourly` 14,827 rows, `fct_daily_congestion` 365 rows |
| Reconciliation | Trips summed over `fct_demand_hourly` and `fct_daily_congestion` equal `fct_monthly_metrics` for all 12 months (42,971,314 in total, 0 mismatches) |
| `python build_dashboard.py` (no `--sample`) | Exit 0, no `Error in` lines, pages screenshotted from the served build. Re-run after the review fixes: exit 0, site in `dashboard/build-real/`, Parquet in `dashboard/parquet/real/`, no `dashboard/build/` left behind |

Figures shown on the pages, checked against direct queries of the database:

| Figure | Value |
|---|---|
| Revenue, whole window | $1,235,223,403 |
| Manhattan pickups per month, before (2024-07 to 2024-12) | 2,992,331 |
| Manhattan pickups per month, after (2025-01 to 2025-06) | 3,262,880 |
| Manhattan average fare, before / after | $16.54 / $15.98 |
| CBD fee share by month, 2025-01 to 2025-06 | 65.6%, 73.8%, 74.0%, 73.7%, 73.0%, 73.5% |
| CBD fee share, daily | n/a on 2025-01-04, 66.2% on 2025-01-05 |
| Monthly fare per mile | $5.55 (2024-08) to $6.13 (2024-12) |
| Monthly tip rate | 21.2% (2024-08) to 22.8% (2025-01, 2025-02) |

These before/after figures are descriptive. The "before" months are July to December and the
"after" months are January to June, so seasonality is mixed in.

### Problems the full data exposed (fixed)

- The before/after table put every "after" month on its own row, because the month was part of the
  group label. It is now one row per period with the months covered.
- Tables stopped at 10 rows and hid months; they now show all rows.
- Month labels on the fare and tip charts were cut to one letter at half width; the charts are now
  full width with short labels (`Jul 24`).
- Axis labels on the borough charts were clipped; they now use millions.

### Congestion marker and time zones

The daily charts plot each day as a plain `YYYY-MM-DD` string on a category axis, and the marker
sits on the category `2025-01-05`. No `Date` object is involved, so the position cannot move with
the viewer's time zone. Before this change the label read "4 Jan 2025" when rendered on the development machine.
The marker was checked on the real-data build.

## Not verified

- **Ubuntu build.** Only Windows was run. The Ubuntu check belongs to the M3 CI workflow.
- **Other time zones.** The marker was checked in one browser time zone. The category axis removes
  the dependence by construction, but it was not re-rendered under a second time zone.
- **Sample run after a real run.** A sample run does not touch `parquet/real/` or `build-real/`; this is
  covered by a unit test (`test_a_sample_run_leaves_the_real_export_and_site_untouched`) and was not
  repeated end to end with both builds.
- **Deferred to M3.** The text-based error matcher and `npm ci` on every build (see `docs/decisions.md`).
