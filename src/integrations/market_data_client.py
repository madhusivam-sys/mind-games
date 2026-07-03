from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Protocol

import httpx
import pandas as pd

from ingestion.session_builder import add_session_columns
from ingestion.validate_data import validate_intraday_frame
from utils.config import get_paths, get_settings
from utils.logging import get_logger
from utils.time import ensure_timestamp

logger = get_logger(__name__)

REQUIRED_MARKET_COLUMNS = [
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "delta",
    "cvd",
    "bid_volume",
    "ask_volume",
]
OPTIONAL_MARKET_COLUMNS = ["oi", "oi_change", "trade_count"]


class MarketDataClientError(RuntimeError):
    """Raised when the external market data client cannot return usable data."""


@dataclass(slots=True)
class MarketDataPayload:
    """Normalized bar payload used by the trading analytics services."""

    frame: pd.DataFrame
    warnings: list[str]
    source_path: Path | str


@dataclass(slots=True)
class TablePayload:
    """Generic tabular payload for supporting TrueData endpoints."""

    frame: pd.DataFrame
    warnings: list[str]
    source_path: Path | str


class MarketDataClient(Protocol):
    """Contract for market data adapters."""

    def fetch_latest(self, symbol: str) -> MarketDataPayload:
        """Return the latest normalized market bar for a symbol."""

    def fetch_history(self, symbol: str, interval: str = "1min", limit: int = 200) -> MarketDataPayload:
        """Return normalized history bars for a symbol."""


class CsvMarketDataClient:
    """CSV-backed market data adapter for the local MVP."""

    def __init__(self, loader: Any | None = None, default_path: Path | None = None) -> None:
        from ingestion.load_csv import CsvDataLoader

        settings = get_settings()
        self.loader = loader or CsvDataLoader(default_symbol=settings.default_symbol)
        self.default_path = default_path or get_paths().sample_csv

    def _load(self, source_path: str | Path | None = None, symbol: str | None = None) -> MarketDataPayload:
        path = Path(source_path) if source_path else self.default_path
        frame, warnings = self.loader.load(path)
        if symbol is not None and "symbol" in frame.columns:
            frame = frame.copy()
            frame["symbol"] = symbol
        return MarketDataPayload(frame=frame, warnings=warnings, source_path=path)

    def fetch_latest(self, symbol: str) -> MarketDataPayload:
        payload = self._load(symbol=symbol)
        return MarketDataPayload(frame=payload.frame.tail(1).reset_index(drop=True), warnings=payload.warnings, source_path=payload.source_path)

    def fetch_history(self, symbol: str, interval: str = "1min", limit: int = 200) -> MarketDataPayload:
        payload = self._load(symbol=symbol)
        return MarketDataPayload(frame=payload.frame.tail(limit).reset_index(drop=True), warnings=payload.warnings, source_path=payload.source_path)


class TrueDataMarketDataClient:
    """TrueData historical REST adapter using bearer-auth CSV endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        bearer_token: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        bidask: int | None = None,
        comp: bool | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.truedata_base_url).rstrip("/")
        self.bearer_token = bearer_token or settings.truedata_bearer_token
        self.timeout_seconds = timeout_seconds or settings.truedata_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.truedata_max_retries
        self.bidask = settings.truedata_bidask if bidask is None else bidask
        self.comp = settings.truedata_comp if comp is None else comp
        self.http_client = http_client or httpx.Client(timeout=self.timeout_seconds)

    def fetch_latest(self, symbol: str) -> MarketDataPayload:
        return self._request_bars(
            path="/getlastnbars",
            symbol=symbol,
            params={"interval": "1min", "nbars": 1, "bidask": self.bidask, "comp": str(self.comp).lower(), "response": "csv"},
        )

    def fetch_history(self, symbol: str, interval: str = "1min", limit: int = 200) -> MarketDataPayload:
        return self._request_bars(
            path="/getlastnbars",
            symbol=symbol,
            params={"interval": interval, "nbars": limit, "bidask": self.bidask, "comp": str(self.comp).lower(), "response": "csv"},
        )

    def fetch_tick_history(self, symbol: str, limit: int = 2000, interval: str = "tick") -> TablePayload:
        return self._request_table(
            path="/getlastnticks",
            params={"symbol": symbol, "nticks": limit, "interval": interval, "bidask": self.bidask, "response": "csv"},
        )

    def fetch_ltp_bulk(self, symbols: list[str]) -> TablePayload:
        return self._request_table(
            path="/getLTPBulk",
            params={"symbols": ",".join(symbols), "response": "csv"},
        )

    def fetch_index_components(self, index_name: str) -> TablePayload:
        return self._request_table(
            path="/getindexcomponents",
            params={"indexname": index_name, "response": "csv"},
        )

    def fetch_option_chain(self, symbol: str, expiry: str) -> TablePayload:
        return self._request_table(
            path="/getSymbolOptionChain",
            params={"symbol": symbol, "expiry": expiry, "response": "csv"},
        )

    def fetch_top_gainers(self, segment: str = "NSEEQ", topn: int = 50) -> TablePayload:
        return self._request_table(
            path="/gettopngainers",
            params={"segment": segment, "topn": topn, "response": "csv"},
        )

    def fetch_top_losers(self, segment: str = "NSEEQ", topn: int = 50) -> TablePayload:
        return self._request_table(
            path="/gettopnlosers",
            params={"segment": segment, "topn": topn, "response": "csv"},
        )

    def _request_bars(self, path: str, symbol: str, params: dict[str, Any]) -> MarketDataPayload:
        table = self._request_table(path=path, params={"symbol": symbol, **params})
        frame, warnings = self._normalize_bar_frame(table.frame, symbol=symbol)
        return MarketDataPayload(frame=frame, warnings=[*table.warnings, *warnings], source_path=table.source_path)

    def _request_table(self, path: str, params: dict[str, Any]) -> TablePayload:
        if not self.base_url:
            raise MarketDataClientError("TRUEDATA_BASE_URL is not configured.")
        if not self.bearer_token:
            raise MarketDataClientError("TRUEDATA_BEARER_TOKEN is not configured.")

        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.http_client.get(url, params=params, headers=headers)
                response.raise_for_status()
                frame = self._parse_csv(response.text)
                normalized = self._normalize_table_frame(frame)
                return TablePayload(frame=normalized, warnings=[], source_path=url)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("TrueData timeout url=%s attempt=%s", url, attempt + 1)
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:200] if exc.response is not None else ""
                raise MarketDataClientError(f"TrueData API error {exc.response.status_code}: {detail}".strip()) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("TrueData HTTP error url=%s attempt=%s error=%s", url, attempt + 1, exc)
            except (ValueError, pd.errors.ParserError) as exc:
                raise MarketDataClientError(f"Unable to parse TrueData CSV response: {exc}") from exc

        raise MarketDataClientError(f"Unable to fetch TrueData market data after {self.max_retries + 1} attempts: {last_error}")

    def _normalize_bar_frame(self, frame: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, list[str]]:
        working = frame.copy()
        rename_map = {
            "date": "timestamp",
            "time": "timestamp",
            "datetime": "timestamp",
            "date_time": "timestamp",
            "ticker": "symbol",
            "instrument": "symbol",
            "ltp": "close",
            "ltq": "volume",
            "vol": "volume",
            "bidvolume": "bid_volume",
            "askvolume": "ask_volume",
            "bid_qty": "bid_volume",
            "ask_qty": "ask_volume",
            "oichange": "oi_change",
            "trades": "trade_count",
        }
        working = working.rename(columns=rename_map)

        if "timestamp" not in working.columns:
            date_column = next((column for column in working.columns if column.startswith("date") or column.startswith("time")), None)
            if date_column is not None:
                working = working.rename(columns={date_column: "timestamp"})

        missing_required = [column for column in ["timestamp", "open", "high", "low", "close"] if column not in working.columns]
        if missing_required:
            raise MarketDataClientError(f"TrueData CSV missing required columns: {missing_required}")

        if "symbol" not in working.columns:
            working["symbol"] = symbol
        if "volume" not in working.columns:
            working["volume"] = pd.NA
        for column in ["delta", "cvd", "bid_volume", "ask_volume", *OPTIONAL_MARKET_COLUMNS]:
            if column not in working.columns:
                working[column] = pd.NA

        working = working[[*REQUIRED_MARKET_COLUMNS, *OPTIONAL_MARKET_COLUMNS]].copy()
        working["timestamp"] = ensure_timestamp(working["timestamp"])
        numeric_columns = [column for column in working.columns if column not in {"timestamp", "symbol"}]
        working[numeric_columns] = working[numeric_columns].apply(pd.to_numeric, errors="coerce")
        working = working.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        validation = validate_intraday_frame(working)
        clean = add_session_columns(validation.frame, default_symbol=symbol)
        return clean.reset_index(drop=True), validation.warnings

    def _parse_csv(self, csv_text: str) -> pd.DataFrame:
        if not csv_text.strip():
            raise MarketDataClientError("TrueData API returned an empty CSV response.")
        frame = pd.read_csv(StringIO(csv_text))
        if frame.empty:
            raise MarketDataClientError("TrueData API returned no rows.")
        return frame

    def _normalize_table_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalized_columns = {column: self._normalize_column_name(column) for column in frame.columns}
        normalized = frame.rename(columns=normalized_columns).copy()
        normalized.columns = [column.lower() for column in normalized.columns]

        timestamp_candidates = [column for column in normalized.columns if column in {"timestamp", "datetime", "date_time"}]
        if timestamp_candidates:
            normalized[timestamp_candidates[0]] = ensure_timestamp(normalized[timestamp_candidates[0]])
        elif {"date", "time"}.issubset(normalized.columns):
            normalized["timestamp"] = ensure_timestamp(normalized["date"].astype(str) + " " + normalized["time"].astype(str))

        return normalized

    @staticmethod
    def _normalize_column_name(column: str) -> str:
        return column.strip().lower().replace(" ", "_")
