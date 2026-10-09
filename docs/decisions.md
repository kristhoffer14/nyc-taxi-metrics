# Design decisions

Choices made while building the project, with the alternatives that were rejected.

## fct_trips is rebuilt when the staging rules change

**Problem.** `fct_trips` is incremental by month and used to reprocess a month only when
`raw.load_log.loaded_at` changed. Changing a staging rule (a threshold in `dbt_project.yml`
or the SQL in `stg_yellow_trips_classified`) left already-built months untouched, so
`fct_trips` silently disagreed with `stg_yellow_trips`. Reproduced on the sample database
by running with `max_trip_distance_miles: 1`: staging dropped to 755 and 764 rows for
2024-12 and 2025-01 while `fct_trips` kept 2945 and 2869.

**Decision.** `fct_trips` stores a `rules_hash` column: an MD5 of the two reject-threshold
variables plus the source of `stg_yellow_trips_classified`, `stg_yellow_trips` and
`stg_taxi_zones` (macro `staging_rules_hash`). A month is reprocessed when it is new,
when its `loaded_at` changed, or when its stored `rules_hash` differs from the current one.
The singular test `assert_fct_trips_matches_staging` compares per-month row counts of
`stg_yellow_trips` and `fct_trips` and fails if they ever diverge.

**Consequences.**
- Editing a rule, even whitespace in those models, rebuilds all months on the next
  `dbt build`. That is a few seconds on DuckDB and keeps the table correct.
- Adding the column changes the table schema (`on_schema_change='fail'`), so a database
  built before this change needs a one-off `dbt build --full-refresh` (or deleting the
  `.duckdb` file and rerunning the pipeline).
- The hash covers the rules, not `fct_trips.sql` itself. Changing the columns of
  `fct_trips` is caught by the contract and `on_schema_change='fail'`.

**Rejected alternatives.**
- *Always full-refresh `fct_trips`:* correct but defeats the incremental requirement in the spec.
- *Only `--full-refresh` from `run_pipeline.py` when it detects a change:* plain
  `cd dbt && dbt build` would still go stale.
- *Compare row counts to decide what to rebuild:* misses rule changes that keep the
  count the same, and needs a scan of staging on every run.
- *Hash only the variables:* misses edits to the rule SQL.

## Dashboard tool: Evidence (open-source build), reading Parquet

**Decision.** The dashboard is an Evidence project in `dashboard/`, built to static HTML with
`npm run build:strict`. The marts are exported to Parquet by `pipeline/export.py`, and Evidence
reads those files through an in-memory DuckDB source (`read_parquet(...)`).

**What was verified (2026-10-09).**
- `@evidence-dev/evidence` 40.1.8 and `@evidence-dev/duckdb` 2.0.1 are the current npm releases, MIT
  licensed and not marked deprecated. The GitHub repository is not archived.
- The current Evidence docs centre on the managed Evidence Studio. The open-source static build
  is documented under `legacy-docs.evidence.dev`, and the `legacy` branch of `evidence-dev/template`
  is the open-source scaffold. Nothing states that it will stop being maintained, but the "legacy"
  label is a risk for the long term.
- A spike on Windows 11 with Node 24.20.0 passed: `npm install`, `npm run sources` and
  `npm run build:strict` succeeded. The Ubuntu build is checked in M3 (CI).

**Gotchas found while building.**
- `@evidence-dev/evidence` 40.1.8 needs exactly `typescript@5.4.2` as a peer; npm otherwise picks
  TypeScript 7 and fails to resolve. It is pinned in `dashboard/package.json`.
- `build:strict` exits 0 even when a page query fails. `pipeline/dashboard.py` therefore scans
  Evidence's output for `Error in ...` and fails the build.
- `build` does not re-read the data; `sources:strict` must run first or a stale cache is used.
- Evidence sorts a categorical x-axis by the y value unless `sort=false` is set, which reordered
  months on the tip-rate chart. All time-ordered line charts set it.
- `LineChart` has no `xMin`/`xMax` props (only `yMin`/`yMax`), so they are silently ignored as
  strings or numbers and a numeric x-axis rounds up to 25. The hour charts plot a zero-padded hour
  label on a category axis (`00` to `23`), full width because half-width charts truncate the labels.
- Daily charts plot dates as `YYYY-MM-DD` strings on a category axis (`xType=category`). A time axis
  turns the strings into `Date` objects, and the 2025-01-05 reference line then depended on the
  viewer's time zone (its label read "4 Jan 2025" when rendered on the development machine).

**Why Parquet instead of the `.duckdb` file.** The connector bundles `@duckdb/node-api ^1.4.x`
while the pipeline writes DuckDB 1.5.5 files. Whether the older reader opens the newer file format
was not verified, and Parquet avoids the question. It also keeps the dashboard independent of dbt:
CI can build the site from the committed fixture without the Node side touching the database.

**Rejected alternatives.**
- *Python-only (Plotly or Altair with Jinja):* one toolchain and no Node, but it departs from the
  spec's preferred tool and means writing the page layout by hand. It remains the fallback if
  Evidence stops building.
- *Reading the `.duckdb` file directly:* fewer steps, but depends on the unverified format
  compatibility above.
- *Querying `fct_trips` from the dashboard:* puts untested SQL in the pages and scans every trip
  at build time. The dashboard reads only contract-tested marts (`fct_demand_hourly`,
  `fct_daily_congestion`, `fct_monthly_metrics`).

## Dashboard output folders: sample and real runs are kept apart

**Decision.** `build_dashboard.py` writes each kind of run to its own folders, so `--sample` can
never overwrite the real-data dashboard:

| | `--sample` | real (no flag) |
|---|---|---|
| Parquet export | `dashboard/parquet/sample/` | `dashboard/parquet/real/` |
| Built site | `dashboard/build/` | `dashboard/build-real/` |

The pages read one fixed folder, `dashboard/parquet/active/`, which each run refills from its own
export just before the Evidence build. All of these are ignored by `dashboard/.gitignore`.

**Why this shape.**
- Evidence's CLI always copies its site to `./build` and ignores `EVIDENCE_BUILD_DIR` for that last
  step, so the real site is moved to `build-real/` by `pipeline/dashboard.py` after the build.
- The sample site stays in `dashboard/build/` because `docs/SPEC.md` (section 7) names
  `dashboard/build/index.html` for `--sample`. The spec is not edited here.
- `build/` is wiped before each build: Evidence copies into it without clearing, so pages from an
  earlier run would otherwise leak into the next one. A real run therefore removes any sample site
  in `build/`; that site is cheap to rebuild.
- *Alternative rejected:* a source query that picks the folder at build time. Evidence source SQL
  has no access to build-time variables, so a fixed `active/` folder is the simplest option.

## The dashboard build checks its result and installs npm packages only when needed

Both items were deferred from Milestone 2 (review of `feat/m2-dashboard`).

**Error matcher.** `run_npm` still scans Evidence's output for `Error in `, which caught real
failures (for example a `printf` type error on the hour charts), but that depends on Evidence's
wording. After the build, `check_site` now also requires every page in `EXPECTED_PAGES`
(`index`, `demand`, `fares`, `congestion`) to exist and to contain no `Error in ` text. A failure
worded differently, or a page that silently did not build, still fails the build and nothing is
moved to the output folder. The list has to be updated when a page is added.

**`npm ci`.** `npm ci` deletes and reinstalls `node_modules`, which is slow. After a successful
install the build stores the SHA-256 of `package-lock.json` in `node_modules/.lockfile-hash`, and
later local builds skip the install while the hash is unchanged. `--force-install` overrides it.
When the `CI` environment variable is `true` (GitHub Actions sets it) the install always runs, so
CI keeps the clean, lockfile-exact install.

**Rejected alternatives.**
- *Always run `npm ci`:* correct, but adds minutes to every local build.
- *Skip whenever `node_modules` exists:* misses a changed lockfile and gives a stale install.
- *Compare file modification times:* unreliable after a git checkout.
- *Only check the pages, drop the text scan:* the scan reports the failing query by name, which
  the page check cannot.

## Why DuckDB, and why not Spark or a warehouse

**Decision.** The engine is DuckDB, driven by dbt-duckdb, in one local file per dataset.

**Why.** The design priorities are correctness, testability, clarity and reproducibility; scale and
cloud services are out of scope (SPEC section 1). The real window of 12 months is 44.9 million
rows. It loads into a 2.7 GB file and `dbt build` took 265 s on the development machine, so a
single process is enough. DuckDB needs no server, account or credentials, reads Parquet directly,
and CI runs the same engine as the development machine.

**Consequences.** One writer at a time: the dashboard export has to open the file after dbt
has finished (the export runs dbt in a child process for this reason). A shared, concurrent
warehouse would need a different adapter.

**Rejected alternatives.**
- *Spark:* the cluster or local JVM setup is far more than 45 million rows need, it slows the
  test loop and CI, and it adds nothing to the correctness goals.
- *PostgreSQL:* needs a server in development and CI; loading Parquet is less direct.
- *BigQuery, Snowflake and other cloud warehouses:* need accounts and credentials, which the
  constraints forbid.
- *pandas only:* no declarative models, tests, contracts or lineage.

## dbt for every transformation

**Decision.** All logic after the raw load is dbt SQL: staging views, mart tables, contracts on
every mart, data tests, unit tests for the fare, tip and invalid-trip rules, and a singular test
that raw rows equal valid plus rejected rows.

**Why.** Each business rule is stated once, in one place, with a test beside it, and the lineage
is generated. Rejected trips are kept in `stg_yellow_trips_rejected` with the first rule they
broke, so the cleaning is auditable and the counts reconcile instead of rows disappearing. The
metric and rule definitions the spec left open are in `docs/spec-change-requests.md` (SCR-1 to
SCR-4).

**Rejected alternatives.** *Plain SQL scripts run from Python:* no dependency graph, no tests or
contracts for free. *Filtering in the loader:* hides what was removed and cannot be tested in SQL.

## Sample and real data never share a database

**Decision.** dbt has two targets: `sample` (default, `data/sample.duckdb`, built from the
committed fixture) and `dev` (`data/nyc_taxi.duckdb`, real data). `run_pipeline.py` chooses the
target itself; a plain `dbt build` uses the sample.

**Why.** A real run skips months that are already loaded, so one shared file would let sample rows
mask real months, or the other way round. The SPEC's M1 check runs `dbt build` on its own after
`--sample`, which only works if the default target is the sample (SCR-3).

## Metrics are ratios of sums

**Decision.** Fare per mile is `sum(fare_amount) / sum(trip_distance)` and tip rate is
`sum(tip_amount) / sum(fare_amount)` on credit-card trips, never an average of per-trip ratios.

**Why.** Per-trip ratios are dominated by very short or very cheap trips. The ratio of sums answers
"how much do riders pay per mile" and can be recomputed from totals. Tip rate excludes cash trips
because cash tips are not recorded (SCR-1; `docs/metrics.md`).

## CI: two jobs, pinned versions, no cache for dbt

**Decision.** `.github/workflows/ci.yml` runs on pull requests only, with `contents: read`, no
secrets and a `concurrency` group that cancels superseded runs.
- Job `python`: `ruff check`, `ruff format --check`, `pytest`, `run_pipeline.py --sample`,
  `dbt build`.
- Job `dashboard`: `build_dashboard.py --sample` (export, `npm ci`, strict Evidence build), a check
  that every page exists, then `build_dashboard.py --published` with the same page check and a check
  that the Pages base path is in the output.
- The runner image is `ubuntu-24.04`, not `latest`. Every action is pinned to a full commit SHA with
  its version in a comment, and Python (3.12) and Node (22) are pinned. pip and npm caches are
  keyed on the requirement files and the lockfile; Python dependencies are pinned in
  `requirements*.txt`.

**Why two jobs.** A lint or test failure and a dashboard failure show up separately, and the two run
in parallel. Node is installed only where it is needed.

**Why no dbt or DuckDB cache.** The sample build takes about ten seconds; a cache adds a way to run
against stale state for no gain.

**Consequences.** Node 22 was chosen as an LTS line while development uses 24; the lockfile is the
same, and the CI run is the evidence that 22 builds. Updating a pinned SHA is a manual step
(Dependabot is not enabled).

## Publishing the dashboard: committed aggregates and GitHub Pages

**Problem.** The README and the live site should show the real 12-month data, but CI only has the
2-month fixture, and the raw trips (725 MB) are never committed.

**Decision.** The three dashboard marts (`fct_monthly_metrics`, `fct_demand_hourly`,
`fct_daily_congestion`) are exported by `python build_dashboard.py --publish-data` into
`dashboard/published-data/` (about 150 KB) with a `metadata.json` giving the data window, the
generation date, the row counts and the valid-trip total. They hold aggregates only: no trip rows,
timestamps, locations or per-trip amounts. `.github/workflows/pages.yml` builds the site from those
files (`build_dashboard.py --published`, with Evidence's base path set to `/nyc-taxi-metrics`) and
deploys it with the official Pages actions on every push to `main`. The workflow uses only the
built-in `GITHUB_TOKEN`: workflow permissions are empty by default, the build job has
`contents: read`, and the deploy job has `pages: write` and `id-token: write`. It never runs on pull
requests. Repository Settings -> Pages -> Source must be set to GitHub Actions once, by the owner.

**What the tests guard.** `tests/test_published_data.py` checks that each file has exactly the
documented aggregate columns, that no column name looks like a trip-level field, that row counts
stay at aggregate scale, that the three files reconcile with each other, that `metadata.json`
matches the files, and (in the slow suite) that the column names and types equal the dbt marts
built from the sample.

**Limitation: stale values are not detected.** The schema test only notices a change in column
names or types. If a staging rule, a metric definition or the source data changes without changing
the columns, the committed Parquet keeps the old numbers and every test still passes. Nothing in CI
recomputes them, because CI does not have the raw data. The project only makes the age visible:
`metadata.json` records the window and the generation date, and the README states them. The
refresh is a manual step, to be run after any change to a model or rule and after extending the
window:

```powershell
python run_pipeline.py                      # real data into data/nyc_taxi.duckdb, dbt build
python build_dashboard.py --publish-data    # rewrite dashboard/published-data/
python scripts/compute_findings.py          # re-check the figures quoted in the README
python build_dashboard.py                   # real-data site for new screenshots in docs/img/
```

then commit the changed files and update the dates in the README.

**Rejected alternatives.**
- *Publish a locally built site (for example a `gh-pages` branch):* nothing data-like in `main`, but
  the site cannot be reproduced from the repository, can drift from the code, and puts megabytes of
  generated files in git history.
- *Pages shows only the sample:* no data to commit, but the public site would show two months and
  the findings could not be explored.
- *Commit the built site:* same history cost as the first option, and a build artifact in `main`.
- *Recompute the marts in CI from the raw files:* would remove the staleness problem, but needs a
  725 MB download and several minutes of dbt on each run, and depends on the TLC servers being up.
- *Commit `fct_trips` or any trip-level data:* too large, and contrary to the rule that raw data is
  never committed.

**Attribution.** Every dashboard page and the README credit "NYC TLC Trip Record Data" with a link
to the TLC page. The TLC page was read on 2026-10-09: it says the trip data was not created by the
TLC and has no endorsement wording, so no endorsement statement is made here.
