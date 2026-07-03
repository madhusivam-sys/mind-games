# clean router


@router.get("/analysis/context")
def analysis_context(
    symbol: str = Query(default_factory=lambda: get_settings().default_symbol),
    interval: str = Query(default="1min"),
    limit: int = Query(default=240, ge=20, le=1000),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.history(symbol=symbol, interval=interval, limit=limit))
    bundle = signal_service.analyze_snapshot(snapshot, symbol=symbol)
    return _build_context_payload(snapshot=snapshot, symbol=symbol, interval=interval, bundle=bundle, include_features=True)


def _build_context_payload(snapshot: MarketDataSnapshot, symbol: str, interval: str, bundle, include_features: bool) -> dict[str, object]:
    prior_summary = _prior_session_summary(bundle.feature_frame)
    signal_snapshot = {
        "scores": [to_jsonifiable(asdict(score)) for score in bundle.latest_scores],
        "watch_scores_1m": [to_jsonifiable(asdict(score)) for score in bundle.watch_scores],
        "alerts": [to_jsonifiable(alert) for alert in bundle.alerts],
        "latest_bar": to_jsonifiable(bundle.feature_frame.iloc[-1].to_dict()),
        "latest_confirmed_bar": to_jsonifiable(bundle.confirmed_feature_frame.iloc[-1].to_dict()) if bundle.confirmed_feature_frame is not None and not bundle.confirmed_feature_frame.empty else None,
    }
    payload: dict[str, object] = {
        "symbol": symbol,
        "interval": interval,
        "source": str(bundle.source_path),
        "data_source": "truedata-rest-history",
        "session_mode": "intraday" if interval == "1min" else "historical",
        "warnings": bundle.warnings,
        "as_of_timestamp": bundle.feature_frame.iloc[-1]["timestamp"].isoformat(),
        "prior_session_summary": prior_summary,
        "model_predictions": _model_predictions(bundle.feature_frame),
        "day_type_summary": _day_type_summary(bundle.feature_frame),
        "auth_status": {"configured": True, "authorized": True, "detail": "Historical market data request succeeded."},
        "signal_snapshot": signal_snapshot,
        "briefing": to_jsonifiable(build_trade_brief(signal_snapshot, prior_summary).to_dict()),
        "bars": [to_jsonifiable(record) for record in snapshot.frame.to_dict(orient="records")],
    }
    if include_features:
        payload["features"] = [to_jsonifiable(record) for record in bundle.feature_frame.to_dict(orient="records")]
    return payload


def _prior_session_summary(feature_frame) -> dict[str, object]:
    previous_session = feature_frame["session_date"].unique()[-2] if feature_frame["session_date"].nunique() > 1 else feature_frame["session_date"].iloc[-1]
    prior = feature_frame[feature_frame["session_date"] == previous_session].iloc[-1]
    return {
        "symbol": prior["symbol"],
        "session_date": prior["session_date"],
        "poc": float(prior["developing_poc"]),
        "vah": float(prior["vah"]),
        "val": float(prior["val"]),
        "h3": float(prior.get("h3", 0.0)),
        "h4": float(prior.get("h4", 0.0)),
        "l3": float(prior.get("l3", 0.0)),
        "l4": float(prior.get("l4", 0.0)),
        "pivot": float(prior.get("pivot", 0.0)),
        "bc": float(prior.get("bc", 0.0)),
        "tc": float(prior.get("tc", 0.0)),
    }


def _model_predictions(feature_frame) -> dict[str, object]:
    predictions: dict[str, object] = {}
    for name in ["day_type_model", "breakout_model", "reversal_model"]:
        try:
            predictions[name] = float(predict_frame(name, feature_frame).iloc[-1])
        except FileNotFoundError:
            predictions[name] = None
    return predictions


def _day_type_summary(feature_frame) -> list[dict[str, Any]]:
    from labels.day_type import label_day_type

    return label_day_type(feature_frame).tail(1).to_dict(orient="records")


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


@router.get("/signals/latest")
def signals_latest(
    symbol: str = Query(default_factory=lambda: get_settings().default_symbol),
    interval: str = Query(default="1min"),
    limit: int = Query(default=200, ge=5, le=1000),
) -> dict[str, object]:
    snapshot = _safe_snapshot(lambda: market_data_service.history(symbol=symbol, interval=interval, limit=limit))
    bundle = signal_service.analyze_snapshot(snapshot, symbol=symbol)
    return _build_context_payload(snapshot=snapshot, symbol=symbol, interval=interval, bundle=bundle, include_features=False)
