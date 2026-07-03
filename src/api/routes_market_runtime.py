

@router.get("/signals/latest")
def signals_latest(
    symbol: str = Query(default_factory=lambda: get_settings().default_symbol),
    interval: str = Query(default="1min"),
    limit: int = Query(default=200, ge=5, le=1000),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.history(symbol=symbol, interval=interval, limit=limit))
    bundle = signal_service.analyze_snapshot(snapshot, symbol=symbol)
    return {
        "symbol": symbol,
        "interval": interval,
        "source": str(bundle.source_path),
        "warnings": bundle.warnings,
        "scores": [to_jsonifiable(asdict(score)) for score in bundle.latest_scores],
        "watch_scores_1m": [to_jsonifiable(asdict(score)) for score in bundle.watch_scores],
        "alerts": [to_jsonifiable(alert) for alert in bundle.alerts],
        "latest_bar": to_jsonifiable(bundle.feature_frame.iloc[-1].to_dict()),
        "latest_confirmed_bar": to_jsonifiable(bundle.confirmed_feature_frame.iloc[-1].to_dict()) if bundle.confirmed_feature_frame is not None and not bundle.confirmed_feature_frame.empty else None,
    }


def _safe_snapshot(loader: Callable[[], MarketDataSnapshot]) -> MarketDataSnapshot:
    try:
        snapshot = loader()
    except MarketDataClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if snapshot.frame.empty:
        raise HTTPException(status_code=404, detail="No market data available for the requested query.")
    return snapshot


def _table_response(snapshot: MarketDataSnapshot, extra: dict[str, object] | None = None) -> dict[str, object]:
    payload = {
        "source": str(snapshot.source_path),
        "warnings": snapshot.warnings,
        "rows": len(snapshot.frame),
        "data": [to_jsonifiable(record) for record in snapshot.frame.to_dict(orient="records")],
    }
    if extra:
        payload.update(extra)
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


@router.get("/market/option-chain")
def market_option_chain(symbol: str = Query(...), expiry: str = Query(...)) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.option_chain(symbol=symbol, expiry=expiry))
    return _table_response(snapshot, extra={"symbol": symbol, "expiry": expiry})


@router.get("/market/top-gainers")
def market_top_gainers(
    segment: str = Query(default="NSEEQ"),
    topn: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.top_gainers(segment=segment, topn=topn))
    return _table_response(snapshot, extra={"segment": segment, "topn": topn})


@router.get("/market/top-losers")
def market_top_losers(
    segment: str = Query(default="NSEEQ"),
    topn: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.top_losers(segment=segment, topn=topn))
    return _table_response(snapshot, extra={"segment": segment, "topn": topn})
