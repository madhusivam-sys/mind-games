from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from integrations.market_data_client import CsvMarketDataClient, MarketDataClient, MarketDataClientError, TablePayload, TrueDataMarketDataClient
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class MarketDataSnapshot:
    """Clean market-data snapshot consumed by downstream services."""

    frame: pd.DataFrame
    warnings: list[str]
    source_path: Path | str


class MarketDataService:
    """Service boundary for loading normalized market data."""

    def __init__(self, client: MarketDataClient | None = None) -> None:
        self.client = client or CsvMarketDataClient()

    def load(self, csv_path: str | Path | None = None, symbol: str | None = None) -> MarketDataSnapshot:
        if not isinstance(self.client, CsvMarketDataClient):
            raise MarketDataClientError("CSV loading is only available when the service uses CsvMarketDataClient.")
        payload = self.client._load(source_path=csv_path, symbol=symbol)
        logger.info("Loaded market data source=%s symbol=%s rows=%s", payload.source_path, symbol, len(payload.frame))
        return MarketDataSnapshot(frame=payload.frame, warnings=payload.warnings, source_path=payload.source_path)

    def latest(self, symbol: str) -> MarketDataSnapshot:
        payload = self.client.fetch_latest(symbol=symbol)
        logger.info("Loaded latest market data source=%s symbol=%s rows=%s", payload.source_path, symbol, len(payload.frame))
        return MarketDataSnapshot(frame=payload.frame, warnings=payload.warnings, source_path=payload.source_path)

    def history(self, symbol: str, interval: str = "1min", limit: int = 200) -> MarketDataSnapshot:
        payload = self.client.fetch_history(symbol=symbol, interval=interval, limit=limit)
        logger.info("Loaded history market data source=%s symbol=%s interval=%s rows=%s", payload.source_path, symbol, interval, len(payload.frame))
        return MarketDataSnapshot(frame=payload.frame, warnings=payload.warnings, source_path=payload.source_path)

    def tick_history(self, symbol: str, limit: int = 2000, interval: str = "tick") -> MarketDataSnapshot:
        payload = self._require_truedata().fetch_tick_history(symbol=symbol, limit=limit, interval=interval)
        return self._from_table_payload(payload)

    def ltp_bulk(self, symbols: list[str]) -> MarketDataSnapshot:
        payload = self._require_truedata().fetch_ltp_bulk(symbols=symbols)
        return self._from_table_payload(payload)

    def index_components(self, index_name: str) -> MarketDataSnapshot:
        payload = self._require_truedata().fetch_index_components(index_name=index_name)
        return self._from_table_payload(payload)

    def option_chain(self, symbol: str, expiry: str) -> MarketDataSnapshot:
        payload = self._require_truedata().fetch_option_chain(symbol=symbol, expiry=expiry)
        return self._from_table_payload(payload)

    def top_gainers(self, segment: str = "NSEEQ", topn: int = 50) -> MarketDataSnapshot:
        payload = self._require_truedata().fetch_top_gainers(segment=segment, topn=topn)
        return self._from_table_payload(payload)

    def top_losers(self, segment: str = "NSEEQ", topn: int = 50) -> MarketDataSnapshot:
        payload = self._require_truedata().fetch_top_losers(segment=segment, topn=topn)
        return self._from_table_payload(payload)

    def _require_truedata(self) -> TrueDataMarketDataClient:
        if not isinstance(self.client, TrueDataMarketDataClient):
            raise MarketDataClientError("This endpoint requires the TrueData market data client.")
        return self.client

    @staticmethod
    def _from_table_payload(payload: TablePayload) -> MarketDataSnapshot:
        return MarketDataSnapshot(frame=payload.frame, warnings=payload.warnings, source_path=payload.source_path)


def build_live_market_data_service() -> MarketDataService:
    """Build the TrueData-backed market data service used by API routes."""

    return MarketDataService(client=TrueDataMarketDataClient())
