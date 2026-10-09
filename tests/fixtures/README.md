# Sample fixture

Used by `python run_pipeline.py --sample` and the tests. No network needed.

| File | Contents |
|---|---|
| `yellow_tripdata_2024-12.parquet` | 3,000 sampled rows + 12 edge cases; **no** `cbd_congestion_fee` column |
| `yellow_tripdata_2025-01.parquet` | 3,000 sampled rows + 12 edge cases; has `cbd_congestion_fee` |
| `taxi_zone_lookup.csv` | Unmodified copy of the TLC zone lookup |

Sampled rows are real TLC trips: each month is sorted by every column and every
Nth row is kept, so the sample is deterministic. The edge cases are copies of one
valid trip with fields overridden to trigger each staging reject rule. They are
listed in `EDGE_CASES` in `scripts/make_fixture.py`.

Regenerate with `python scripts/make_fixture.py` (downloads the two months if
needed). Output is byte-identical for the pinned DuckDB version.
