import pytest

from pipeline import config


def test_month_range_crosses_year_boundary():
    assert config.month_range("2024-11", "2025-02") == ["2024-11", "2024-12", "2025-01", "2025-02"]


def test_month_range_single_month():
    assert config.month_range("2025-01", "2025-01") == ["2025-01"]


def test_default_window_has_twelve_months():
    assert len(config.month_range(config.DEFAULT_START, config.DEFAULT_END)) == 12


@pytest.mark.parametrize("bad", ["2025-13", "2025-00", "2025-1", "25-01", "2025/01", ""])
def test_invalid_month_is_rejected(bad):
    with pytest.raises(ValueError, match="Invalid month"):
        config.Month.parse(bad)


def test_start_after_end_is_rejected():
    with pytest.raises(ValueError, match="after end month"):
        config.month_range("2025-02", "2025-01")


def test_trip_url_and_filename():
    assert config.trip_filename("2025-01") == "yellow_tripdata_2025-01.parquet"
    assert config.trip_url("2025-01") == (
        "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-01.parquet"
    )
