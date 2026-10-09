import re
import subprocess
import sys

import pytest

from pipeline import config


def run_findings():
    return subprocess.run(
        [sys.executable, "scripts/compute_findings.py"],
        cwd=config.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def findings():
    result = run_findings()
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def readme():
    text = (config.ROOT / "README.md").read_text(encoding="utf-8")
    return " ".join(text.split())  # the README wraps lines; compare on one line


def test_compute_findings_runs_on_the_published_data():
    result = run_findings()

    assert result.returncode == 0, result.stderr
    assert "Window 2024-07 to 2025-06" in result.stdout
    assert "not causal" in result.stdout


def section(text, start, end=None):
    """The part of the script output between two headings."""
    begin = text.index(start)
    return text[begin : text.index(end, begin)] if end else text[begin:]


def pairs(text, pattern):
    return [m.groups() for m in re.finditer(pattern, text, re.MULTILINE)]


def quoted(readme, fragment):
    assert fragment in readme, f"README no longer says: {fragment!r}; re-check compute_findings.py"


def test_readme_demand_figures_match_the_script(findings, readme):
    demand = section(findings, "1. Demand", "2. Fare per mile")
    boroughs = dict(pairs(demand, r"^\s{4}([A-Za-z ]+?)\s+([\d.]+)%$"))
    busiest_hour, busiest_share = re.search(
        r"Busiest hours.*?\n\s+(\d\d:00)\s+([\d.]+)%", demand, re.DOTALL
    ).groups()
    quietest_hour, quietest_share = re.search(
        r"Quietest hour.*?\n\s+(\d\d:00)\s+([\d.]+)%", demand, re.DOTALL
    ).groups()
    weekdays = {int(d): int(n.replace(",", "")) for d, n in pairs(demand, r"^\s+(\d)\s+([\d,]+)$")}

    quoted(
        readme,
        f"Manhattan has {boroughs['Manhattan']}% of pickups and Queens {boroughs['Queens']}%",
    )
    quoted(readme, f"The busiest hour is {busiest_hour} ({busiest_share}% of trips)")
    quoted(readme, f"the quietest is {quietest_hour} ({quietest_share}%)")
    # README: Thursday is the busiest weekday and Monday the quietest.
    assert max(weekdays, key=weekdays.get) == 4
    assert min(weekdays, key=weekdays.get) == 1
    quoted(readme, f"(about {round(weekdays[4], -3):,} trips a day)")
    quoted(readme, f"Monday the quietest (about {round(weekdays[1], -3):,})")


def test_readme_fare_and_tip_figures_match_the_script(findings, readme):
    monthly = pairs(
        section(findings, "2. Fare per mile", "3. Share of trips"),
        r"^\s+(\d{4}-\d\d)\s+\$\s*([\d.]+)\s+([\d.]+)%$",
    )
    fares = {month: fare for month, fare, _ in monthly}
    tips = {month: tip for month, _, tip in monthly}
    low_month = min(fares, key=lambda m: float(fares[m]))
    high_month = max(fares, key=lambda m: float(fares[m]))
    top_tip = max(tips.values(), key=float)
    top_tip_months = ", ".join(m for m, t in tips.items() if t == top_tip)
    low_tip_month = min(tips, key=lambda m: float(tips[m]))
    recent = [fares[m] for m in fares if "2025-02" <= m <= "2025-06"]

    assert high_month == "2024-12"  # README: "peaked in December"
    quoted(readme, f"${fares[low_month]} ({low_month}) to ${fares[high_month]} ({high_month})")
    quoted(readme, f"${min(recent, key=float)} to ${max(recent, key=float)} from February to June")
    quoted(readme, f"{tips[low_tip_month]}% ({low_tip_month}) to {top_tip}% ({top_tip_months})")


def test_readme_congestion_fee_figures_match_the_script(findings, readme):
    block = section(findings, "3. Share of trips", "4. Manhattan pickups")
    shares = pairs(block, r"^\s+(\d{4}-\d\d)\s+([\d.]+)%$")
    first_month, first_share = shares[0]
    later = [float(share) for _, share in shares[1:]]
    first_day = re.search(r"first tolled day [\d-]+: ([\d.]+)%", block).group(1)

    quoted(readme, f"{first_share}% in {first_month}")
    quoted(readme, f"{min(later):.1f}% to {max(later):.1f}% from February to June")
    quoted(readme, f"On the first tolled day it was {first_day}%")


def test_readme_before_after_figures_match_the_script(findings, readme):
    block = section(findings, "4. Manhattan pickups", "Manhattan pickup trips by month")
    rows = {
        period: (trips, fare)
        for period, trips, fare in pairs(
            block, r"^\s+(Before|After)\s+.*?([\d,]+) trips/month\s+\$([\d.]+)$"
        )
    }
    trips_sign, trips_change, fare_sign, fare_change = re.search(
        r"change in trips per month ([+-])([\d.]+)%, in average fare ([+-])([\d.]+)%", block
    ).groups()
    by_month = dict(
        pairs(
            section(findings, "Manhattan pickup trips by month"),
            r"^\s+(\d{4}-\d\d)\s+([\d,]+)$",
        )
    )
    lowest = sorted(by_month, key=lambda m: int(by_month[m].replace(",", "")))[:2]
    lowest_millions = [int(by_month[m].replace(",", "")) / 1e6 for m in sorted(lowest)]

    for period in ("Before", "After"):
        trips, fare = rows[period]
        quoted(readme, f"| {period} | ")
        quoted(readme, f"| {trips} | ${fare} |")
    quoted(
        readme, f"Trips per month are {trips_change}% {'higher' if trips_sign == '+' else 'lower'}"
    )
    quoted(readme, f"the average fare {fare_change}% {'higher' if fare_sign == '+' else 'lower'}")
    # README: July and August are the two lowest months.
    assert sorted(lowest) == ["2024-07", "2024-08"]
    quoted(readme, f"({lowest_millions[0]:.1f} and {lowest_millions[1]:.1f} million Manhattan")


def test_readme_window_and_valid_trip_count_match_the_script(findings, readme):
    valid_trips = re.search(r"([\d,]+) valid trips", findings).group(1)

    quoted(readme, f"({valid_trips} valid trips)")
    quoted(readme, "2024-07 to 2025-06")
