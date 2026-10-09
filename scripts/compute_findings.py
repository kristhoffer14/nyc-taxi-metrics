"""Print the figures quoted in the README, computed from the committed aggregated marts.

Usage: python scripts/compute_findings.py
Reads dashboard/published-data/ only; no database or network is needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

DATA = Path(__file__).resolve().parent.parent / "dashboard" / "published-data"
MONTHLY = (DATA / "fct_monthly_metrics.parquet").as_posix()
HOURLY = (DATA / "fct_demand_hourly.parquet").as_posix()
DAILY = (DATA / "fct_daily_congestion.parquet").as_posix()


def rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    return con.execute(sql).fetchall()


def main() -> int:
    metadata = json.loads((DATA / "metadata.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    print(
        f"Window {metadata['first_month']} to {metadata['last_month']}, "
        f"{metadata['valid_trips']:,} valid trips, data generated {metadata['generated_on']}\n"
    )

    print("1. Demand")
    print("  Share of trips by pickup borough:")
    for borough, share in rows(
        con,
        f"SELECT pickup_borough, sum(trips) / sum(sum(trips)) OVER () "
        f"FROM '{HOURLY}' GROUP BY 1 ORDER BY 2 DESC",
    ):
        print(f"    {borough:<14}{share:7.1%}")
    print("  Busiest hours (share of all trips):")
    for hour, share in rows(
        con,
        f"SELECT pickup_hour, sum(trips) / sum(sum(trips)) OVER () "
        f"FROM '{HOURLY}' GROUP BY 1 ORDER BY 2 DESC LIMIT 3",
    ):
        print(f"    {hour:02d}:00{share:9.1%}")
    print("  Quietest hour (share of all trips):")
    for hour, share in rows(
        con,
        f"SELECT pickup_hour, sum(trips) / sum(sum(trips)) OVER () "
        f"FROM '{HOURLY}' GROUP BY 1 ORDER BY 2 LIMIT 1",
    ):
        print(f"    {hour:02d}:00{share:9.1%}")
    print("  Average trips per day by weekday (1 = Monday), whole window:")
    for day, avg in rows(
        con,
        f"""
        WITH days AS (
            SELECT dayofweek(date_day - 1) + 1 AS iso_day, sum(trips) AS trips, count(*) AS n
            FROM '{DAILY}' GROUP BY 1
        )
        SELECT iso_day, trips / n FROM days ORDER BY 1
        """,
    ):
        print(f"    {day}  {avg:12,.0f}")

    print("\n2. Fare per mile and tip rate by month")
    for month, fpm, tip in rows(
        con,
        f"SELECT year_month, fare_per_mile_usd, tip_rate FROM '{MONTHLY}' ORDER BY month_start",
    ):
        print(f"    {month}  ${fpm:5.2f}  {tip:6.1%}")

    print("\n3. Share of trips with the congestion fee, by month")
    for month, share in rows(
        con,
        f"SELECT year_month, cbd_fee_trip_share FROM '{MONTHLY}' "
        f"WHERE cbd_fee_trip_share IS NOT NULL ORDER BY month_start",
    ):
        print(f"    {month}  {share:6.1%}")
    first_day = rows(
        con,
        f"SELECT date_day, cbd_fee_trip_share FROM '{DAILY}' "
        f"WHERE is_congestion_pricing_active ORDER BY date_day LIMIT 1",
    )[0]
    print(f"    first tolled day {first_day[0]}: {first_day[1]:.1%}")

    print("\n4. Manhattan pickups, months before vs after tolling (descriptive, not causal)")
    for period, months, covered, trips, fare in rows(
        con,
        f"""
        SELECT CASE WHEN is_congestion_pricing_month THEN 'After' ELSE 'Before' END,
               count(*), min(year_month) || ' to ' || max(year_month),
               sum(manhattan_pickup_trips) / count(*),
               sum(manhattan_pickup_avg_fare_usd * manhattan_pickup_trips)
                   / sum(manhattan_pickup_trips)
        FROM '{MONTHLY}' GROUP BY is_congestion_pricing_month ORDER BY 1 DESC
        """,
    ):
        print(
            f"    {period:<7}{covered}  ({months} months)  {trips:12,.0f} trips/month  ${fare:.2f}"
        )
    before, after = (
        rows(
            con,
            f"SELECT sum(manhattan_pickup_trips) / count(*), "
            f"sum(manhattan_pickup_avg_fare_usd * manhattan_pickup_trips) "
            f"/ sum(manhattan_pickup_trips) FROM '{MONTHLY}' "
            f"WHERE is_congestion_pricing_month = {flag}",
        )[0]
        for flag in ("false", "true")
    )
    print(f"    change in trips per month {after[0] / before[0] - 1:+.1%}, ", end="")
    print(f"in average fare {after[1] / before[1] - 1:+.1%}")
    print(
        "    Same months in the previous year are not in the data, so seasonality is not removed."
    )

    print("\nManhattan pickup trips by month")
    for month, trips in rows(
        con, f"SELECT year_month, manhattan_pickup_trips FROM '{MONTHLY}' ORDER BY month_start"
    ):
        print(f"    {month}  {trips:10,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
