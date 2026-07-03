from __future__ import annotations

import pandas as pd

from ingestion.load_csv import CsvDataLoader
from rules.setup_scores import ScoreResult
from services.live_signal_service import LiveBarAggregator, LiveSignalService
from services.signal_service import AnalysisBundle, SignalService
from utils.config import get_paths, get_settings


class StubSignalService:
    def __init__(self) -> None:
        self.calls: list[pd.DataFrame] = []

    def analyze_snapshot(self, snapshot, symbol: str | None = None) -> AnalysisBundle:
        self.calls.append(snapshot.frame.copy())
        return AnalysisBundle(
            feature_frame=snapshot.frame.copy(),
            latest_scores=[],
            alerts=[],
            warnings=[],
            source_path=snapshot.source_path,
        )


def test_live_bar_aggregator_rolls_ticks_into_closed_bars() -> None:
    aggregator = LiveBarAggregator(timeframe="1min", default_symbol="NIFTY-I")

    assert aggregator.ingest_tick({"timestamp": "2026-03-18 09:15:05", "symbol": "NIFTY-I", "ltp": 22450, "ltq": 10, "bid_qty": 4, "ask_qty": 6}) is None
    assert aggregator.ingest_tick({"timestamp": "2026-03-18 09:15:40", "symbol": "NIFTY-I", "ltp": 22455, "ltq": 5, "bid_qty": 2, "ask_qty": 3}) is None

    completed = aggregator.ingest_tick({"timestamp": "2026-03-18 09:16:00", "symbol": "NIFTY-I", "ltp": 22460, "ltq": 8, "bid_qty": 3, "ask_qty": 5})

    assert completed is not None
    assert completed["open"] == 22450.0
    assert completed["high"] == 22455.0
    assert completed["low"] == 22450.0
    assert completed["close"] == 22455.0
    assert completed["volume"] == 15.0
    assert completed["delta"] == 3.0


def test_live_bar_aggregator_keeps_symbols_isolated() -> None:
    aggregator = LiveBarAggregator(timeframe="1min", default_symbol="NIFTY-I")

    aggregator.ingest_tick({"timestamp": "2026-03-18 09:15:05", "symbol": "NIFTY-I", "ltp": 22450, "ltq": 10})
    aggregator.ingest_tick({"timestamp": "2026-03-18 09:15:10", "symbol": "BANKNIFTY-I", "ltp": 50000, "ltq": 12})
    first = aggregator.ingest_tick({"timestamp": "2026-03-18 09:16:00", "symbol": "NIFTY-I", "ltp": 22455, "ltq": 8})
    second = aggregator.ingest_tick({"timestamp": "2026-03-18 09:16:00", "symbol": "BANKNIFTY-I", "ltp": 50010, "ltq": 6})

    assert first is not None and second is not None
    assert first["symbol"] == "NIFTY-I"
    assert second["symbol"] == "BANKNIFTY-I"


def test_live_signal_service_scores_only_after_bar_close() -> None:
    stub = StubSignalService()
    service = LiveSignalService(signal_service=stub, aggregator=LiveBarAggregator(timeframe="1min", default_symbol="BANKNIFTY-I"))

    assert service.on_trade({"timestamp": "2026-03-18 09:15:01", "symbol": "BANKNIFTY-I", "ltp": 50000, "ltq": 10, "bid_qty": 4, "ask_qty": 6}) is None
    assert stub.calls == []

    bundle = service.on_trade({"timestamp": "2026-03-18 09:16:00", "symbol": "BANKNIFTY-I", "ltp": 50010, "ltq": 8, "bid_qty": 3, "ask_qty": 5})

    assert bundle is not None
    assert len(stub.calls) == 1
    analyzed = stub.calls[0]
    assert analyzed.iloc[-1]["close"] == 50000.0
    assert analyzed.iloc[-1]["symbol"] == "BANKNIFTY-I"
    assert "session_date" in analyzed.columns
    assert "minutes_from_open" in analyzed.columns


def test_live_signal_service_real_engine_path_runs() -> None:
    loader = CsvDataLoader(default_symbol=get_settings().default_symbol)
    frame, _warnings = loader.load(get_paths().sample_csv)
    seed = frame.head(14)

    service = LiveSignalService(signal_service=SignalService())
    service.seed_history(seed)

    bundle = service.on_trade({
        "timestamp": seed.iloc[-1]["timestamp"] + pd.Timedelta(minutes=1),
        "symbol": seed.iloc[-1]["symbol"],
        "ltp": float(seed.iloc[-1]["close"] + 5),
        "ltq": 10,
        "bid_qty": 4,
        "ask_qty": 6,
    })
    assert bundle is None

    bundle = service.on_trade({
        "timestamp": seed.iloc[-1]["timestamp"] + pd.Timedelta(minutes=2),
        "symbol": seed.iloc[-1]["symbol"],
        "ltp": float(seed.iloc[-1]["close"] + 6),
        "ltq": 12,
        "bid_qty": 5,
        "ask_qty": 7,
    })

    assert bundle is not None
    assert len(bundle.latest_scores) == 7
    assert "vwap" in bundle.feature_frame.columns
    assert "session_date" in bundle.feature_frame.columns


def test_live_signal_service_builds_callbacks() -> None:
    service = LiveSignalService(signal_service=StubSignalService())
    callbacks = service.build_callbacks()

    assert callbacks.on_trade == service.on_trade
    assert callbacks.on_bar == service.on_bar
    assert callbacks.on_bidask == service.on_bidask
    assert callbacks.on_greek == service.on_greek


def test_signal_service_keeps_one_minute_watch_until_full_five_bar_close() -> None:
    from services.market_data_service import MarketDataSnapshot

    class IdentityStore:
        def build(self, frame: pd.DataFrame) -> pd.DataFrame:
            return frame.copy()

    class FixedScoreEngine:
        def score_row(self, row: pd.Series):
            return [
                ScoreResult(
                    timestamp=row["timestamp"],
                    symbol=row["symbol"],
                    setup_name="responsive_buy",
                    score=80,
                    label="buy",
                    reasons=["Test setup active."],
                    invalidation="Test invalidation.",
                    summary="Responsive Buy is buy because Test setup active.",
                )
            ]

    class NoopAlertEngine:
        def build(self, frame: pd.DataFrame):
            return []

    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-03-18 09:15:00", periods=9, freq="min"),
            "symbol": ["NIFTY-I"] * 9,
            "open": [100.0 + i for i in range(9)],
            "high": [101.0 + i for i in range(9)],
            "low": [99.0 + i for i in range(9)],
            "close": [100.5 + i for i in range(9)],
            "volume": [10.0] * 9,
            "delta": [1.0] * 9,
            "cvd": list(range(9)),
            "bid_volume": [4.0] * 9,
            "ask_volume": [6.0] * 9,
            "session_date": ["2026-03-18"] * 9,
            "bar_index": list(range(9)),
            "typical_price": [100.0 + i for i in range(9)],
            "minutes_from_open": list(range(9)),
        }
    )

    service = SignalService(store=IdentityStore(), score_engine=FixedScoreEngine(), alert_engine=NoopAlertEngine())
    bundle = service.analyze_snapshot(MarketDataSnapshot(frame=frame, warnings=[], source_path="mock://snapshot"), symbol="NIFTY-I")

    assert bundle.watch_scores[0].label == "watch"
    assert bundle.latest_scores[0].label == "buy"
    assert bundle.confirmed_feature_frame is not None
    assert len(bundle.confirmed_feature_frame) == 1
    assert bundle.confirmed_feature_frame.iloc[-1]["timestamp"] == pd.Timestamp("2026-03-18 09:19:00")



