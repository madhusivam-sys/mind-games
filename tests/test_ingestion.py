from __future__ import annotations

from ingestion.load_csv import CsvDataLoader
from utils.config import repo_path


def test_csv_loader_builds_session_metadata() -> None:
    frame, warnings = CsvDataLoader().load(repo_path("data", "samples", "nifty_futures_sample.csv"))
    assert warnings == []
    assert {"session_date", "bar_index", "typical_price", "minutes_from_open"}.issubset(frame.columns)
    assert frame["timestamp"].is_monotonic_increasing
    assert frame["symbol"].eq("NIFTY_FUT").all()
