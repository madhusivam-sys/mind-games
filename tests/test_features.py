from __future__ import annotations

from features.feature_store import load_sample_features
from features.market_profile import MarketProfileEngine
from ingestion.load_csv import CsvDataLoader
from utils.config import repo_path


def test_feature_store_builds_requested_feature_columns() -> None:
    frame = load_sample_features()
    expected = {"developing_poc", "vah", "val", "hvn", "lvn", "rolling_delta", "h3", "pivot", "vwap", "atr_regime"}
    assert expected.issubset(frame.columns)
    assert frame[["timestamp", "symbol", "session_date"]].duplicated().sum() == 0


def test_feature_store_no_forward_fill_breaks_shape() -> None:
    frame = load_sample_features()
    assert len(frame) > 0
    assert frame["poc_migration"].iloc[0] == 0.0


def test_poor_extreme_flags_are_prefix_stable() -> None:
    raw, _warnings = CsvDataLoader().load(repo_path("data", "samples", "nifty_futures_sample.csv"))
    first_session = raw[raw["session_date"] == raw["session_date"].iloc[0]].reset_index(drop=True)
    short = first_session.iloc[:6].copy()

    short_features = MarketProfileEngine().transform(short)
    long_features = MarketProfileEngine().transform(first_session).iloc[:6].reset_index(drop=True)

    assert short_features["poor_high"].equals(long_features["poor_high"])
    assert short_features["poor_low"].equals(long_features["poor_low"])
