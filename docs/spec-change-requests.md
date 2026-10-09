# Spec change requests

Proposed clarifications to `docs/SPEC.md`. The spec is not edited directly; each
item records the decision taken in the meantime. SCR-1 to SCR-4 were incorporated
into `docs/SPEC.md` on the `feat/m2-dashboard` branch with the owner's approval.

## SCR-1: Define revenue, fare per mile and tip rate (Milestone 1)

**Gap:** Section 2 names these metrics without defining them.
**Proposal:** Revenue = `sum(total_amount)`. Fare per mile =
`sum(fare_amount) / sum(trip_distance)` over trips with distance > 0. Tip rate =
`sum(tip_amount) / sum(fare_amount)` over credit-card trips with fare > 0. All
ratios are ratios of sums.
**Status:** Implemented as proposed (tip rate and aggregation confirmed by the
project owner); see `docs/metrics.md`. Incorporated into SPEC.md (section 2).

## SCR-2: Congestion pricing start date (Milestone 1)

**Gap:** Section 2 says congestion pricing "started in January 2025". Tolling began
on 2025-01-05.
**Proposal:** State the exact date. Monthly views treat 2025-01 as the first
"after" month; daily views use the exact date.
**Status:** Implemented via the dbt var `congestion_pricing_start_date`. Incorporated into
SPEC.md (section 2).

## SCR-3: Which database `cd dbt && dbt build` targets (Milestone 1)

**Gap:** The M1 criterion runs `dbt build` on its own after
`run_pipeline.py --sample`, but sample and real data must not share one database
(real runs would skip months already loaded from the sample).
**Proposal:** dbt has two targets: `sample` (default, `data/sample.duckdb`) and
`dev` (real data, `data/nyc_taxi.duckdb`). A plain `dbt build` uses the sample;
`dbt build --target dev` uses real data. `run_pipeline.py` picks the target itself.
**Status:** Implemented. Incorporated into SPEC.md (section 4).

## SCR-4: Pickup-month rule checks pickup only (Milestone 1)

**Gap:** Section 3 lists "timestamps outside the file's month" as a quality issue.
**Proposal:** Reject a trip when its pickup is outside the file's month. A dropoff
in the next month is valid (trips that cross midnight on the last day).
**Status:** Implemented as rule `pickup_outside_source_month`. Incorporated into SPEC.md
(section 3).

## SCR-5: CI scope and the public site (Milestone 3)

**Gap:** Section 5 (CI) lists ruff, pytest, `run_pipeline.py --sample` and `dbt build`; it does not
mention the dashboard build, and the spec has no place for publishing the site. Section 7 names
`dashboard/build/index.html` for `--sample`, but real-data and published sites need their own folders.
**Proposal:** CI also builds the dashboard from the sample and from the committed aggregates in
`dashboard/published-data/`. A separate workflow publishes the real-data site to GitHub Pages on
pushes to `main`, using only the built-in `GITHUB_TOKEN`. Output folders: `build/` (sample),
`build-real/` (real run), `build-published/` (committed aggregates).
**Status:** Implemented; see "Publishing the dashboard" in `docs/decisions.md`.
