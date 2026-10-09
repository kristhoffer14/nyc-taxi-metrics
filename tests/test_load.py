import duckdb
import pytest

from pipeline import load

TRIP_SELECT = """
    SELECT
        2::INTEGER AS VendorID,
        TIMESTAMP '{month}-05 10:00:00' + to_minutes(i) AS tpep_pickup_datetime,
        TIMESTAMP '{month}-05 10:20:00' + to_minutes(i) AS tpep_dropoff_datetime,
        1::BIGINT AS passenger_count,
        2.5 AS trip_distance,
        1::BIGINT AS RatecodeID,
        'N' AS store_and_fwd_flag,
        161 AS PULocationID,
        236 AS DOLocationID,
        1::BIGINT AS payment_type,
        15.0 AS fare_amount,
        1.0 AS extra,
        0.5 AS mta_tax,
        3.0 AS tip_amount,
        0.0 AS tolls_amount,
        1.0 AS improvement_surcharge,
        23.0 AS total_amount,
        2.5 AS congestion_surcharge,
        0.0 AS Airport_fee
        {extra}
    FROM range({rows}) t(i)
"""


def write_trips(path, month, rows, extra=""):
    sql = TRIP_SELECT.format(month=month, rows=rows, extra=extra)
    duckdb.sql(f"COPY ({sql}) TO '{path.as_posix()}' (FORMAT parquet)")
    return path


@pytest.fixture
def zone_csv(tmp_path):
    path = tmp_path / "zones.csv"
    path.write_text(
        '"LocationID","Borough","Zone","service_zone"\n'
        '161,"Manhattan","Midtown Center","Yellow Zone"\n'
        '236,"Manhattan","Upper East Side North","Yellow Zone"\n'
    )
    return path


@pytest.fixture
def files(tmp_path):
    return {
        "2024-12": write_trips(tmp_path / "2024-12.parquet", "2024-12", 5),
        "2025-01": write_trips(
            tmp_path / "2025-01.parquet", "2025-01", 7, extra=", 0.75 AS cbd_congestion_fee"
        ),
    }


def count_rows(db_path, where="true"):
    with duckdb.connect(str(db_path), read_only=True) as con:
        return con.execute(f"SELECT count(*) FROM raw.yellow_trips WHERE {where}").fetchone()[0]


def test_loads_months_and_zones(tmp_path, files, zone_csv):
    db = tmp_path / "t.duckdb"
    results = load.load_all(db, files, zone_csv)
    assert [(r.month, r.rows, r.skipped) for r in results] == [
        ("2024-12", 5, False),
        ("2025-01", 7, False),
    ]
    assert count_rows(db) == 12
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM raw.taxi_zones").fetchone()[0] == 2


def test_rerun_is_idempotent_and_skips(tmp_path, files, zone_csv):
    db = tmp_path / "t.duckdb"
    load.load_all(db, files, zone_csv)
    results = load.load_all(db, files, zone_csv)
    assert all(r.skipped for r in results)
    assert count_rows(db) == 12


def test_force_replaces_rows_without_duplicates(tmp_path, files, zone_csv):
    db = tmp_path / "t.duckdb"
    load.load_all(db, files, zone_csv)
    results = load.load_all(db, files, zone_csv, force=True)
    assert not any(r.skipped for r in results)
    assert count_rows(db) == 12


def test_missing_cbd_fee_column_loads_as_null(tmp_path, files, zone_csv):
    db = tmp_path / "t.duckdb"
    load.load_all(db, files, zone_csv)
    assert count_rows(db, "source_month = '2024-12' AND cbd_congestion_fee IS NULL") == 5
    assert count_rows(db, "source_month = '2025-01' AND cbd_congestion_fee = 0.75") == 7


def test_column_names_match_case_insensitively(tmp_path, files, zone_csv):
    db = tmp_path / "t.duckdb"
    load.load_all(db, files, zone_csv)
    assert count_rows(db, "airport_fee = 0.0 AND vendorid = 2") == 12


def test_missing_required_column_fails_loudly(tmp_path, zone_csv):
    path = tmp_path / "bad.parquet"
    duckdb.sql(f"COPY (SELECT 1 AS VendorID) TO '{path.as_posix()}' (FORMAT parquet)")
    with pytest.raises(load.SchemaError, match="missing required columns"):
        load.load_all(tmp_path / "t.duckdb", {"2025-01": path}, zone_csv)


def test_failed_load_leaves_no_partial_month(tmp_path, files, zone_csv):
    db = tmp_path / "t.duckdb"
    load.load_all(db, files, zone_csv)
    bad = tmp_path / "bad.parquet"
    duckdb.sql(
        f"COPY (SELECT 'x' AS VendorID, * EXCLUDE (VendorID) FROM '{files['2024-12'].as_posix()}') "
        f"TO '{bad.as_posix()}' (FORMAT parquet)"
    )
    with pytest.raises(duckdb.ConversionException):
        load.load_all(db, {"2024-12": bad}, zone_csv, force=True)
    assert count_rows(db, "source_month = '2024-12'") == 5
