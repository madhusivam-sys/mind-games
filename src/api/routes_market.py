
from __future__ import annotations

from dataclasses import asdict
from typing import Callable
from fastapi import APIRouter, HTTPException, Query

from integrations.live_market_data_client import LiveMarketDataClientError
from integrations.market_data_client import MarketDataClientError
from services.live_runtime import LiveRuntime
from services.market_data_service import MarketDataSnapshot, build_live_market_data_service
from services.signal_service import SignalService, to_jsonifiable
from utils.config import get_settings

router = APIRouter(tags=["market-data"])
market_data_service = build_live_market_data_service()
signal_service = SignalService(market_data_service=market_data_service)
live_runtime = LiveRuntime(market_data_service=market_data_service)

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": get_settings().app_name}


@router.post("/live/start")
def live_start(symbols: str | None = Query(default=None, description="Optional comma-separated symbols for live backfill.")) -> dict[str, object]:
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()] if symbols else None
    try:
        status = live_runtime.start(symbols=symbol_list)
    except LiveMarketDataClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return asdict(status)


@router.post("/live/stop")
def live_stop() -> dict[str, object]:
    status = live_runtime.stop()
    return asdict(status)


@router.get("/live/status")
def live_status() -> dict[str, object]:
    return asdict(live_runtime.status())


@router.get("/live/signals/latest")
def live_signals_latest() -> dict[str, object]:
    try:
        payload = live_runtime.latest_signals()
    except LiveMarketDataClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    payload["scores"] = [to_jsonifiable(score) for score in payload["scores"]]
    payload["watch_scores_1m"] = [to_jsonifiable(score) for score in payload.get("watch_scores_1m", [])]
    payload["latest_bar"] = to_jsonifiable(payload["latest_bar"])
    return payload


@router.get("/live/snapshot")
def live_snapshot(include_open_bar: bool = Query(default=True)) -> dict[str, object]:
    try:
        payload = live_runtime.latest_snapshot(include_open_bar=include_open_bar)
    except LiveMarketDataClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    payload["data"] = [to_jsonifiable(record) for record in payload["data"]]
    return payload

@router.get("/market/latest")
def market_latest(symbol: str = Query(default_factory=lambda: get_settings().default_symbol)) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.latest(symbol=symbol))
    return {
        "symbol": symbol,
        "source": str(snapshot.source_path),
        "warnings": snapshot.warnings,
        "data": to_jsonifiable(snapshot.frame.iloc[-1].to_dict()),
    }


@router.get("/market/history")
def market_history(
    symbol: str = Query(default_factory=lambda: get_settings().default_symbol),
    interval: str = Query(default="1min"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.history(symbol=symbol, interval=interval, limit=limit))
    return _table_response(snapshot, extra={"symbol": symbol, "interval": interval})


@router.get("/market/ticks")
def market_ticks(
    symbol: str = Query(default_factory=lambda: get_settings().default_symbol),
    limit: int = Query(default=200, ge=1, le=5000),
    interval: str = Query(default="tick"),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.tick_history(symbol=symbol, limit=limit, interval=interval))
    return _table_response(snapshot, extra={"symbol": symbol, "interval": interval})


@router.get("/market/ltp-bulk")
def market_ltp_bulk(symbols: str = Query(..., description="Comma-separated symbols.")) -> dict[str, object]:
    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    snapshot = _safe_snapshot(lambda: market_data_service.ltp_bulk(symbols=symbol_list))
    return _table_response(snapshot, extra={"symbols": symbol_list})


@router.get("/market/index-components")
def market_index_components(index_name: str = Query(..., alias="indexName")) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.index_components(index_name=index_name))
    return _table_response(snapshot, extra={"index_name": index_name})
