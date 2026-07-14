from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from integrations.market_data_client import MarketDataClientError
from labels.day_type import label_day_type
from models.predict import predict_frame
from models.registry import DEMO_MODEL_NOTICE, DEMO_MODEL_STATUS
from services.briefing import build_trade_brief
from services.market_data_service import build_live_market_data_service
from services.signal_service import SignalService, to_jsonifiable
from utils.config import get_settings

router = APIRouter(tags=["analysis-context"])
market_data_service = build_live_market_data_service()
signal_service = SignalService(market_data_service=market_data_service)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _session_summary(feature_frame) -> dict[str, object]:
    previous_session = feature_frame["session_date"].unique()[-2] if feature_frame["session_date"].nunique() > 1 else feature_frame["session_date"].iloc[-1]
    prior = feature_frame[feature_frame["session_date"] == previous_session].iloc[-1]
    close = _safe_float(prior.get("close"), 0.0)
    poc = _safe_float(prior.get("developing_poc"), close)
    vah = _safe_float(prior.get("vah"), close)
    val = _safe_float(prior.get("val"), close)
    return {
        "symbol": str(prior.get("symbol", "")),
        "session_date": str(prior.get("session_date", "")),
        "poc": poc,
        "vah": vah,
        "val": val,
        "h3": _safe_float(prior.get("h3"), 0.0),
        "h4": _safe_float(prior.get("h4"), 0.0),
        "l3": _safe_float(prior.get("l3"), 0.0),
        "l4": _safe_float(prior.get("l4"), 0.0),
        "pivot": _safe_float(prior.get("pivot"), 0.0),
        "bc": _safe_float(prior.get("bc"), 0.0),
        "tc": _safe_float(prior.get("tc"), 0.0),
    }


def _model_predictions(feature_frame) -> dict[str, object]:
    predictions: dict[str, object] = {
        "model_status": DEMO_MODEL_STATUS,
        "model_notice": DEMO_MODEL_NOTICE,
    }
    for name in ["day_type_model", "breakout_model", "reversal_model"]:
        try:
            predictions[name] = float(predict_frame(name, feature_frame).iloc[-1])
        except (FileNotFoundError, KeyError, ValueError):
            predictions[name] = None
    return predictions


def _day_type_summary(feature_frame) -> list[dict[str, Any]]:
    try:
        return label_day_type(feature_frame).tail(1).to_dict(orient="records")
    except KeyError:
        return []


@router.get("/market/auth-status")
def market_auth_status(symbol: str = Query(default="NIFTY-I")) -> dict[str, object]:
    settings = get_settings()
    if not settings.truedata_bearer_token:
        return {
            "configured": False,
            "authorized": False,
            "detail": "TRUEDATA_BEARER_TOKEN is not configured.",
            "symbol": symbol,
            "as_of": None,
        }
    try:
        snapshot = market_data_service.history(symbol=symbol, interval="1min", limit=1)
    except MarketDataClientError as exc:
        return {
            "configured": True,
            "authorized": False,
            "detail": str(exc),
            "symbol": symbol,
            "as_of": None,
        }
    return {
        "configured": True,
        "authorized": True,
        "detail": "TrueData historical REST auth is working.",
        "symbol": symbol,
        "as_of": snapshot.frame.iloc[-1]["timestamp"].isoformat() if not snapshot.frame.empty else None,
    }


@router.get("/analysis/context")
def analysis_context(
    symbol: str = Query(default="NIFTY-I"),
    interval: str = Query(default="1min"),
    limit: int = Query(default=240, ge=20, le=1000),
) -> dict[str, object]:
    try:
        snapshot = market_data_service.history(symbol=symbol, interval=interval, limit=limit)
    except MarketDataClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if snapshot.frame.empty:
        raise HTTPException(status_code=404, detail="No market data available for the requested query.")

    bundle = signal_service.analyze_snapshot(snapshot, symbol=symbol)
    prior_summary = _session_summary(bundle.feature_frame)
    signal_snapshot = {
        "scores": [to_jsonifiable(asdict(score)) for score in bundle.latest_scores],
        "watch_scores_1m": [to_jsonifiable(asdict(score)) for score in bundle.watch_scores],
        "alerts": [to_jsonifiable(alert) for alert in bundle.alerts],
        "latest_bar": to_jsonifiable(bundle.feature_frame.iloc[-1].to_dict()),
        "latest_confirmed_bar": to_jsonifiable(bundle.confirmed_feature_frame.iloc[-1].to_dict()) if bundle.confirmed_feature_frame is not None and not bundle.confirmed_feature_frame.empty else None,
    }
    return {
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
        "auth_status": {
            "configured": True,
            "authorized": True,
            "detail": "Historical market data request succeeded.",
        },
        "signal_snapshot": signal_snapshot,
        "briefing": to_jsonifiable(build_trade_brief(signal_snapshot, prior_summary).to_dict()),
        "bars": [to_jsonifiable(record) for record in snapshot.frame.to_dict(orient="records")],
        "features": [to_jsonifiable(record) for record in bundle.feature_frame.to_dict(orient="records")],
    }
