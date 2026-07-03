from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from fastapi.testclient import TestClient

from api import routes_market
from api.main import app
from rules.setup_scores import ScoreResult
from services.live_runtime import LiveRuntimeStatus
from services.market_data_service import MarketDataSnapshot
from services.signal_service import AnalysisBundle

client = TestClient(app)


@dataclass
class FakeMarketDataService:
    frame: pd.DataFrame

    def latest(self, symbol: str) -> MarketDataSnapshot:
        frame = self.frame.copy()
        frame["symbol"] = symbol
        return MarketDataSnapshot(frame=frame.tail(1).reset_index(drop=True), warnings=[], source_path="mock://latest")

    def history(self, symbol: str, interval: str = "1m", limit: int = 200) -> MarketDataSnapshot:
        frame = self.frame.tail(limit).copy().reset_index(drop=True)
        frame["symbol"] = symbol
        return MarketDataSnapshot(frame=frame, warnings=[], source_path=f"mock://history/{interval}")


@dataclass
class FakeSignalService:
    frame: pd.DataFrame

    def analyze_snapshot(self, snapshot: MarketDataSnapshot, symbol: str | None = None) -> AnalysisBundle:
        latest_symbol = symbol or snapshot.frame.iloc[-1]["symbol"]
        scores = [
            ScoreResult(
                timestamp=snapshot.frame.iloc[-1]["timestamp"],
                symbol=latest_symbol,
                setup_name="responsive_buy",
                score=78,
                label="buy",
                reasons=["POC is migrating higher."],
                invalidation="Invalidate below VAL.",
                summary="Responsive Buy is buy because POC is migrating higher.",
            )
        ]
        watch_scores = [
            ScoreResult(
                timestamp=snapshot.frame.iloc[-1]["timestamp"],
                symbol=latest_symbol,
                setup_name="responsive_buy",
                score=78,
                label="watch",
                reasons=["1-minute setup is active pending 5-minute close."],
                invalidation="Invalidate below VAL.",
                summary="Responsive Buy is watch because 1-minute setup is active pending 5-minute close.",
            )
        ]
        return AnalysisBundle(
            feature_frame=self.frame.copy(),
            latest_scores=scores,
            alerts=[],
            warnings=[],
            source_path="mock://signals",
            watch_scores=watch_scores,
            confirmed_feature_frame=self.frame.tail(5).copy(),
        )


@dataclass
class FakeLiveRuntime:
    frame: pd.DataFrame

    def __post_init__(self) -> None:
        self.started = False

    def start(self, symbols: list[str] | None = None) -> LiveRuntimeStatus:
        self.started = True
        return LiveRuntimeStatus(running=True, source="truedata-live", completed_bars=2, has_analysis=True)

    def stop(self) -> LiveRuntimeStatus:
        self.started = False
        return LiveRuntimeStatus(running=False, source="truedata-live", completed_bars=2, has_analysis=True)

    def status(self) -> LiveRuntimeStatus:
        return LiveRuntimeStatus(running=self.started, source="truedata-live", completed_bars=2, has_analysis=True)

    def latest_signals(self) -> dict[str, object]:
        return {
            "source": "truedata-live",
            "warnings": [],
            "scores": [{
                "timestamp": self.frame.iloc[-1]["timestamp"],
                "symbol": self.frame.iloc[-1]["symbol"],
                "setup_name": "responsive_buy",
                "score": 80,
                "label": "buy",
                "reasons": ["VWAP reclaim held."],
                "invalidation": "Lose VWAP.",
                "summary": "Responsive Buy is buy because VWAP reclaim held.",
            }],
            "watch_scores_1m": [{
                "timestamp": self.frame.iloc[-1]["timestamp"],
                "symbol": self.frame.iloc[-1]["symbol"],
                "setup_name": "responsive_buy",
                "score": 80,
                "label": "watch",
                "reasons": ["1-minute reclaim is active pending 5-minute close."],
                "invalidation": "Lose VWAP.",
                "summary": "Responsive Buy is watch because 1-minute reclaim is active pending 5-minute close.",
            }],
            "latest_bar": self.frame.iloc[-1].to_dict(),
        }

    def latest_snapshot(self, include_open_bar: bool = True) -> dict[str, object]:
        return {
            "source": "truedata-live",
            "warnings": [],
            "rows": len(self.frame),
            "data": self.frame.to_dict(orient="records"),
        }


base_frame = pd.DataFrame(
    {
        "timestamp": pd.date_range("2026-03-16 09:15:00", periods=25, freq="min"),
        "symbol": ["NIFTY_FUT"] * 25,
        "open": [22450 + i for i in range(25)],
        "high": [22455 + i for i in range(25)],
        "low": [22445 + i for i in range(25)],
        "close": [22452 + i for i in range(25)],
        "volume": [1000 + 10 * i for i in range(25)],
        "delta": [5] * 25,
        "cvd": list(range(25)),
        "bid_volume": [500] * 25,
        "ask_volume": [505] * 25,
        "session_date": ["2026-03-16"] * 25,
        "bar_index": list(range(25)),
        "typical_price": [22450.0 + i for i in range(25)],
        "minutes_from_open": list(range(25)),
        "vwap": [22451.0 + i for i in range(25)],
    }
)

routes_market.market_data_service = FakeMarketDataService(base_frame)
routes_market.signal_service = FakeSignalService(base_frame)
routes_market.live_runtime = FakeLiveRuntime(base_frame.tail(2).reset_index(drop=True))


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_signal_endpoint_smoke() -> None:
    response = client.post("/signals", json={})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["setup_name"] == "responsive_buy"


def test_market_latest_endpoint_smoke() -> None:
    response = client.get("/market/latest", params={"symbol": "BANKNIFTY_FUT"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BANKNIFTY_FUT"
    assert payload["data"]["symbol"] == "BANKNIFTY_FUT"


def test_market_history_endpoint_smoke() -> None:
    response = client.get("/market/history", params={"symbol": "NIFTY_FUT", "limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == 10
    assert len(payload["data"]) == 10


def test_signals_latest_endpoint_smoke() -> None:
    response = client.get("/signals/latest", params={"symbol": "NIFTY_FUT", "limit": 25})
    assert response.status_code == 200
    payload = response.json()
    assert payload["scores"][0]["setup_name"] == "responsive_buy"
    assert payload["scores"][0]["label"] == "buy"
    assert payload["watch_scores_1m"][0]["label"] == "watch"
    assert payload["latest_bar"]["symbol"] == "NIFTY_FUT"
    assert payload["latest_confirmed_bar"] is not None


def _fake_tick_history(self: FakeMarketDataService, symbol: str, limit: int = 2000, interval: str = "tick") -> MarketDataSnapshot:
    frame = self.frame.tail(limit).copy().reset_index(drop=True)
    frame["symbol"] = symbol
    frame["price"] = frame["close"]
    return MarketDataSnapshot(frame=frame[["timestamp", "symbol", "price", "bid_volume", "ask_volume"]], warnings=[], source_path=f"mock://ticks/{interval}")


def _fake_ltp_bulk(self: FakeMarketDataService, symbols: list[str]) -> MarketDataSnapshot:
    frame = pd.DataFrame({"symbol": symbols, "ltp": [100.0 + index for index, _ in enumerate(symbols)]})
    return MarketDataSnapshot(frame=frame, warnings=[], source_path="mock://ltp-bulk")


def _fake_index_components(self: FakeMarketDataService, index_name: str) -> MarketDataSnapshot:
    frame = pd.DataFrame({"index_name": [index_name, index_name], "symbol": ["RELIANCE", "HDFCBANK"]})
    return MarketDataSnapshot(frame=frame, warnings=[], source_path="mock://index-components")


def _fake_option_chain(self: FakeMarketDataService, symbol: str, expiry: str) -> MarketDataSnapshot:
    frame = pd.DataFrame({"symbol": [symbol], "expiry": [expiry], "strike": [25000], "option_type": ["CE"], "ltp": [125.5]})
    return MarketDataSnapshot(frame=frame, warnings=[], source_path="mock://option-chain")


def _fake_top_gainers(self: FakeMarketDataService, segment: str = "NSEEQ", topn: int = 50) -> MarketDataSnapshot:
    frame = pd.DataFrame({"segment": [segment], "symbol": ["ABC"], "change_pct": [4.2]})
    return MarketDataSnapshot(frame=frame, warnings=[], source_path="mock://top-gainers")


def _fake_top_losers(self: FakeMarketDataService, segment: str = "NSEEQ", topn: int = 50) -> MarketDataSnapshot:
    frame = pd.DataFrame({"segment": [segment], "symbol": ["XYZ"], "change_pct": [-3.7]})
    return MarketDataSnapshot(frame=frame, warnings=[], source_path="mock://top-losers")


FakeMarketDataService.tick_history = _fake_tick_history
FakeMarketDataService.ltp_bulk = _fake_ltp_bulk
FakeMarketDataService.index_components = _fake_index_components
FakeMarketDataService.option_chain = _fake_option_chain
FakeMarketDataService.top_gainers = _fake_top_gainers
FakeMarketDataService.top_losers = _fake_top_losers


def test_market_ticks_endpoint_smoke() -> None:
    response = client.get("/market/ticks", params={"symbol": "NIFTY-I", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NIFTY-I"
    assert payload["rows"] == 5


def test_market_ltp_bulk_endpoint_smoke() -> None:
    response = client.get("/market/ltp-bulk", params={"symbols": "NIFTY-I,BANKNIFTY-I"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbols"] == ["NIFTY-I", "BANKNIFTY-I"]
    assert payload["rows"] == 2


def test_market_option_chain_endpoint_smoke() -> None:
    response = client.get("/market/option-chain", params={"symbol": "NIFTY", "expiry": "250327"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NIFTY"
    assert payload["data"][0]["expiry"] == "250327"


def test_live_status_endpoint_smoke() -> None:
    response = client.get("/live/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "truedata-live"
    assert payload["completed_bars"] == 2


def test_live_snapshot_endpoint_smoke() -> None:
    response = client.get("/live/snapshot")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == 2


def test_live_signals_latest_endpoint_smoke() -> None:
    response = client.get("/live/signals/latest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scores"][0]["setup_name"] == "responsive_buy"
    assert payload["watch_scores_1m"][0]["label"] == "watch"


def test_live_start_stop_endpoints_smoke() -> None:
    start_response = client.post("/live/start")
    stop_response = client.post("/live/stop")
    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert start_response.json()["running"] is True
    assert stop_response.json()["running"] is False

from api import routes_context

routes_context.market_data_service = FakeMarketDataService(base_frame)
routes_context.signal_service = FakeSignalService(base_frame)


def test_analysis_context_endpoint_smoke() -> None:
    response = client.get("/analysis/context", params={"symbol": "NIFTY_FUT", "interval": "1min", "limit": 25})
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NIFTY_FUT"
    assert payload["briefing"]["primary_setup"]["setup_name"] == "responsive_buy"
    assert payload["signal_snapshot"]["watch_scores_1m"][0]["label"] == "watch"
    assert payload["data_source"] == "truedata-rest-history"


def test_market_auth_status_endpoint_smoke() -> None:
    response = client.get("/market/auth-status", params={"symbol": "NIFTY_FUT"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["authorized"] is True
    assert payload["symbol"] == "NIFTY_FUT"
routes_context.get_settings = lambda: type('Settings', (), {'truedata_bearer_token': 'test-token'})()
