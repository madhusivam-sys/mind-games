from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import pandas as pd

from ingestion.session_builder import add_session_columns
from ingestion.validate_data import validate_intraday_frame
from integrations.live_market_data_client import LiveCallbacks
from services.market_data_service import MarketDataSnapshot
from services.signal_service import AnalysisBundle, SignalService
from utils.logging import get_logger

logger = get_logger(__name__)

BAR_COLUMNS = ["timestamp", "symbol", "open", "high", "low", "close", "volume", "delta", "cvd", "bid_volume", "ask_volume"]


@dataclass(slots=True)
class LiveBar:
    """Mutable representation of the current in-progress intraday bar."""

    timestamp: pd.Timestamp
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    delta: float
    cvd: float
    bid_volume: float
    ask_volume: float

    def update(self, price: float, size: float, delta: float, cvd: float | None, bid_volume: float, ask_volume: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += size
        self.delta += delta
        self.bid_volume += bid_volume
        self.ask_volume += ask_volume
        if cvd is not None:
            self.cvd = cvd
        else:
            self.cvd += delta

    def to_record(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "delta": self.delta,
            "cvd": self.cvd,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
        }


class LiveBarAggregator:
    """Aggregate live ticks into closed intraday bars for downstream analytics."""

    def __init__(self, timeframe: str = "1min", max_bars: int = 500, default_symbol: str = "NIFTY_FUT") -> None:
        self.timeframe = timeframe
        self.max_bars = max_bars
        self.default_symbol = default_symbol
        self._completed: deque[dict[str, object]] = deque(maxlen=max_bars)
        self._current_bars: dict[str, LiveBar] = {}

    def ingest_tick(self, payload: Any) -> dict[str, object] | None:
        tick = self._normalize_tick(payload)
        symbol = str(tick["symbol"])
        bucket = tick["timestamp"].floor(self.timeframe)
        current = self._current_bars.get(symbol)

        if current is None:
            self._current_bars[symbol] = self._make_bar(bucket, tick)
            return None

        if bucket < current.timestamp:
            logger.warning("Ignoring out-of-order tick for symbol=%s timestamp=%s current_bucket=%s", symbol, tick["timestamp"], current.timestamp)
            return None

        if bucket > current.timestamp:
            completed = current.to_record()
            self._completed.append(completed)
            self._current_bars[symbol] = self._make_bar(bucket, tick)
            return completed

        current.update(
            price=tick["price"],
            size=tick["size"],
            delta=tick["delta"],
            cvd=tick["cvd"],
            bid_volume=tick["bid_volume"],
            ask_volume=tick["ask_volume"],
        )
        return None

    def ingest_bar(self, payload: Any) -> dict[str, object]:
        bar = self._normalize_bar(payload)
        symbol = str(bar["symbol"])
        self._completed.append(bar)
        self._current_bars.pop(symbol, None)
        return bar

    def seed_history(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        history = frame.copy()
        for column in BAR_COLUMNS:
            if column not in history.columns:
                history[column] = pd.NA
        history = history[BAR_COLUMNS].copy()
        history["timestamp"] = pd.to_datetime(history["timestamp"])
        history = history.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        for record in history.to_dict(orient="records"):
            self._completed.append(record)
        logger.info("Seeded live aggregator with %s historical bars", len(history))

    def to_frame(self, include_open_bar: bool = False) -> pd.DataFrame:
        records = list(self._completed)
        if include_open_bar and self._current_bars:
            records.extend(bar.to_record() for bar in self._current_bars.values())
        frame = pd.DataFrame(records)
        if frame.empty:
            return frame
        return frame.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    @property
    def completed_bars(self) -> int:
        return len(self._completed)

    def _make_bar(self, bucket: pd.Timestamp, tick: dict[str, object]) -> LiveBar:
        price = float(tick["price"])
        size = float(tick["size"])
        delta = float(tick["delta"])
        cvd_value = tick["cvd"]
        cvd = float(cvd_value) if cvd_value is not None else float(delta)
        return LiveBar(
            timestamp=bucket,
            symbol=str(tick["symbol"]),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=size,
            delta=delta,
            cvd=cvd,
            bid_volume=float(tick["bid_volume"]),
            ask_volume=float(tick["ask_volume"]),
        )

    def _normalize_tick(self, payload: Any) -> dict[str, object]:
        data = self._as_mapping(payload)
        timestamp = self._coerce_timestamp(self._first_value(data, ["timestamp", "time", "date_time", "datetime"]))
        symbol = str(self._first_value(data, ["symbol", "ticker", "instrument"], default=self.default_symbol))
        price = float(self._first_value(data, ["ltp", "price", "last_price", "close"]))
        size = float(self._first_value(data, ["ltq", "last_traded_qty", "size", "volume"], default=0.0))
        bid_volume = float(self._first_value(data, ["bid_volume", "bid_qty", "bidquantity"], default=0.0))
        ask_volume = float(self._first_value(data, ["ask_volume", "ask_qty", "askquantity"], default=0.0))
        delta = data.get("delta")
        if delta is None:
            delta = ask_volume - bid_volume if ask_volume or bid_volume else 0.0
        cvd = data.get("cvd")
        return {
            "timestamp": timestamp,
            "symbol": symbol,
            "price": price,
            "size": size,
            "delta": float(delta),
            "cvd": None if cvd is None else float(cvd),
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
        }

    def _normalize_bar(self, payload: Any) -> dict[str, object]:
        data = self._as_mapping(payload)
        timestamp = self._coerce_timestamp(self._first_value(data, ["timestamp", "time", "date_time", "datetime"]))
        symbol = str(self._first_value(data, ["symbol", "ticker", "instrument"], default=self.default_symbol))
        close = float(self._first_value(data, ["close", "ltp", "price"]))
        open_price = float(self._first_value(data, ["open"], default=close))
        high = float(self._first_value(data, ["high"], default=close))
        low = float(self._first_value(data, ["low"], default=close))
        volume = float(self._first_value(data, ["volume", "vol", "ltq"], default=0.0))
        bid_volume = float(self._first_value(data, ["bid_volume", "bid_qty"], default=0.0))
        ask_volume = float(self._first_value(data, ["ask_volume", "ask_qty"], default=0.0))
        delta = float(self._first_value(data, ["delta"], default=ask_volume - bid_volume))
        cvd = float(self._first_value(data, ["cvd"], default=delta))
        return {
            "timestamp": timestamp.floor(self.timeframe),
            "symbol": symbol,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "delta": delta,
            "cvd": cvd,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
        }

    @staticmethod
    def _as_mapping(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if hasattr(payload, "__dict__"):
            return {key: value for key, value in vars(payload).items() if not key.startswith("_")}
        raise ValueError("Live market payload must be dict-like or expose a __dict__.")

    @staticmethod
    def _coerce_timestamp(value: Any) -> pd.Timestamp:
        return pd.Timestamp(value)

    @staticmethod
    def _first_value(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        if default is not None:
            return default
        raise ValueError(f"Missing required live market field from candidates: {keys}")


class LiveSignalService:
    """Stream live ticks into bars and score only completed bars."""

    def __init__(self, signal_service: SignalService | None = None, aggregator: LiveBarAggregator | None = None, source_name: str = "truedata-live") -> None:
        self.signal_service = signal_service or SignalService()
        self.aggregator = aggregator or LiveBarAggregator()
        self.source_name = source_name
        self.latest_analysis: AnalysisBundle | None = None

    def build_callbacks(self) -> LiveCallbacks:
        return LiveCallbacks(
            on_trade=self.on_trade,
            on_bar=self.on_bar,
            on_bidask=self.on_bidask,
            on_greek=self.on_greek,
        )

    def seed_history(self, frame: pd.DataFrame) -> None:
        self.aggregator.seed_history(frame)

    def on_trade(self, payload: Any) -> AnalysisBundle | None:
        completed = self.aggregator.ingest_tick(payload)
        if completed is None:
            return None
        return self._analyze_completed_bars(symbol=str(completed["symbol"]))

    def on_bar(self, payload: Any) -> AnalysisBundle | None:
        completed = self.aggregator.ingest_bar(payload)
        return self._analyze_completed_bars(symbol=str(completed["symbol"]))

    def on_bidask(self, payload: Any) -> None:
        logger.debug("Received bidask payload=%s", payload)

    def on_greek(self, payload: Any) -> None:
        logger.debug("Received greek payload=%s", payload)

    def latest_snapshot(self, include_open_bar: bool = False) -> MarketDataSnapshot:
        frame = self._normalized_frame(include_open_bar=include_open_bar)
        return MarketDataSnapshot(frame=frame, warnings=[], source_path=self.source_name)

    def _analyze_completed_bars(self, symbol: str) -> AnalysisBundle | None:
        frame = self._normalized_frame(include_open_bar=False)
        if frame.empty:
            return None
        snapshot = MarketDataSnapshot(frame=frame, warnings=[], source_path=self.source_name)
        self.latest_analysis = self.signal_service.analyze_snapshot(snapshot, symbol=symbol)
        return self.latest_analysis

    def _normalized_frame(self, include_open_bar: bool) -> pd.DataFrame:
        frame = self.aggregator.to_frame(include_open_bar=include_open_bar)
        if frame.empty:
            return frame
        validation = validate_intraday_frame(frame)
        normalized = add_session_columns(validation.frame, default_symbol=self.aggregator.default_symbol)
        numeric_columns = [column for column in normalized.columns if column not in {"timestamp", "symbol", "session_date"}]
        normalized[numeric_columns] = normalized[numeric_columns].apply(pd.to_numeric, errors="coerce")
        return normalized.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
