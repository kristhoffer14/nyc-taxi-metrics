import duckdb

from pipeline import config

MAX_FIXTURE_BYTES = 2 * 1024 * 1024


def test_fixture_fits_size_budget():
    total = sum(p.stat().st_size for p in config.FIXTURES_DIR.iterdir() if p.is_file())
    assert total <= MAX_FIXTURE_BYTES


def test_fixture_covers_schema_with_and_without_cbd_fee():
    columns = {}
    for month in config.SAMPLE_MONTHS:
        path = config.FIXTURES_DIR / config.trip_filename(month)
        described = duckdb.sql(f"DESCRIBE SELECT * FROM '{path.as_posix()}'").fetchall()
        columns[month] = {row[0] for row in described}
    assert "cbd_congestion_fee" not in columns["2024-12"]
    assert "cbd_congestion_fee" in columns["2025-01"]
