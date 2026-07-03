from __future__ import annotations

import pandas as pd

from rules.setup_scores import ScoreResult
from services.live_runtime import LiveRuntime
from services.market_data_service import MarketDataSnapshot
from services.signal_service import AnalysisBundle


class FakeMarketDataService:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls: list[tuple[str, str, int]] = []

    def history(self, symbol: str, interval: str = "1min", limit: int = 200) -> MarketDataSnapshot:
        self.calls.append((symbol, interval, limit))
        seed = self.frame.copy()
        seed["symbol"] = symbol
        return MarketDataSnapshot(frame=seed, warnings=[], source_path=f"mock://history/{symbol}")


class FakeLiveClient:
    def __init__(self) -> None:
        self.callbacks = None
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        return self

    def stop(self) -> None:
        self.stopped = True


class FakeLiveService:
    def __init__(self, frame: pd.DataFrame, analysis: AnalysisBundle) -> None:
        self.source_name = "truedata-live"
        self.aggregator = type("Agg", (), {"completed_bars": len(frame)})()
        self._frame = frame
        self.latest_analysis = analysis
        self.seeded: list[pd.DataFrame] = []

    def build_callbacks(self):
        return object()

    def seed_history(self, frame: pd.DataFrame) -> None:
        self.seeded.append(frame.copy())

    def latest_snapshot(self, include_open_bar: bool = False) -> MarketDataSnapshot:
        return MarketDataSnapshot(frame=self._frame.copy(), warnings=[], source_path="truedata-live")


def test_live_runtime_seeds_backfill_and_serializes_scores() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-03-18 09:15:00", periods=3, freq="min"),
            "symbol": ["NIFTY-I"] * 3,
            "open": [1.0, 2.0, 3.0],
            "high": [1.0, 2.0, 3.0],
            "low": [1.0, 2.0, 3.0],
            "close": [1.0, 2.0, 3.0],
            "volume": [1.0, 1.0, 1.0],
            "delta": [0.0, 0.0, 0.0],
            "cvd": [0.0, 0.0, 0.0],
            "bid_volume": [0.0, 0.0, 0.0],
            "ask_volume": [0.0, 0.0, 0.0],
            "session_date": ["2026-03-18"] * 3,
            "bar_index": [0, 1, 2],
            "typical_price": [1.0, 2.0, 3.0],
            "minutes_from_open": [0, 1, 2],
            "distance_to_poc": [0.0, 0.0, 0.0],
            "distance_to_vah": [0.0, 0.0, 0.0],
            "distance_to_val": [0.0, 0.0, 0.0],
            "distance_to_vwap": [0.0, 0.0, 0.0],
            "aggression_score": [10.0, 10.0, 10.0],
            "cvd_slope": [0.0, 0.0, 0.0],
            "delta_slope": [0.0, 0.0, 0.0],
            "imbalance_cluster_count": [0.0, 0.0, 0.0],
            "poc_migration": [0.0, 0.0, 0.0],
            "breakout_through_lvn": [0, 0, 0],
        }
    )
    analysis = AnalysisBundle(
        feature_frame=frame,
        latest_scores=[
            ScoreResult(
                timestamp=frame.iloc[-1]["timestamp"],
                symbol="NIFTY-I",
                setup_name="responsive_buy",
                score=80,
                label="buy",
                reasons=["Value held."],
                invalidation="Lose value.",
                summary="Responsive Buy is buy because Value held.",
            )
        ],
        alerts=[],
        warnings=[],
        source_path="truedata-live",
        watch_scores=[
            ScoreResult(
                timestamp=frame.iloc[-1]["timestamp"],
                symbol="NIFTY-I",
                setup_name="responsive_buy",
                score=80,
                label="watch",
                reasons=["1-minute value hold is active pending 5-minute close."],
                invalidation="Lose value.",
                summary="Responsive Buy is watch because 1-minute value hold is active pending 5-minute close.",
            )
        ],
    )

    live_service = FakeLiveService(frame, analysis)
    live_client = FakeLiveClient()
    market_data_service = FakeMarketDataService(frame[["timestamp", "symbol", "open", "high", "low", "close", "volume", "delta", "cvd", "bid_volume", "ask_volume"]])

    runtime = LiveRuntime(live_service=live_service, live_client=live_client, market_data_service=market_data_service)
    status = runtime.start(symbols=["NIFTY-I"])
    payload = runtime.latest_signals()

    assert status.running is True
    assert market_data_service.calls == [("NIFTY-I", "1min", 200)]
    assert len(live_service.seeded) == 1
    assert payload["scores"][0]["setup_name"] == "responsive_buy"
    assert payload["watch_scores_1m"][0]["label"] == "watch"
    assert "day_type_model" in payload["model_predictions"]
