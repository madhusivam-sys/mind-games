from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd
from fastapi import APIRouter

from api.schemas import AnalyzeRequest, UploadResponse
from labels.day_type import label_day_type
from models.predict import predict_frame
from services.market_data_service import MarketDataService
from services.signal_service import SignalService, to_jsonifiable
from utils.config import get_paths, get_settings

router = APIRouter()
market_data_service = MarketDataService()
signal_service = SignalService(market_data_service=market_data_service)


def build_analysis(csv_path: str | None = None, symbol: str | None = None) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    bundle = signal_service.analyze(csv_path=csv_path, symbol=symbol)
    scores = [to_jsonifiable(asdict(result)) for result in bundle.latest_scores]
    alerts = [to_jsonifiable(alert) for alert in bundle.alerts]
    return bundle.feature_frame, scores, alerts


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": get_settings().app_name}


@router.post("/upload", response_model=UploadResponse)
def upload_data(request: AnalyzeRequest) -> UploadResponse:
    settings = get_settings()
    path = Path(request.csv_path) if request.csv_path else get_paths().sample_csv
    snapshot = market_data_service.load(path, request.symbol)
    frame = snapshot.frame
    if request.symbol and request.symbol != settings.default_symbol:
        frame = frame.copy()
        frame["symbol"] = request.symbol
    return UploadResponse(rows=len(frame), warnings=snapshot.warnings)


@router.post("/snapshot")
def latest_snapshot(request: AnalyzeRequest) -> dict[str, object]:
    features, _scores, _alerts = build_analysis(request.csv_path, request.symbol)
    return to_jsonifiable(features.iloc[-1].to_dict())


@router.post("/signals")
def current_signals(request: AnalyzeRequest) -> list[dict[str, object]]:
    _features, scores, _alerts = build_analysis(request.csv_path, request.symbol)
    return scores


@router.post("/alerts")
def current_alerts(request: AnalyzeRequest) -> list[dict[str, object]]:
    _features, _scores, alerts = build_analysis(request.csv_path, request.symbol)
    return alerts


@router.post("/prior-session-summary")
def prior_session_summary(request: AnalyzeRequest) -> dict[str, object]:
    features, _scores, _alerts = build_analysis(request.csv_path, request.symbol)
    previous_session = features["session_date"].unique()[-2] if features["session_date"].nunique() > 1 else features["session_date"].iloc[-1]
    prior = features[features["session_date"] == previous_session].iloc[-1]
    return {"symbol": prior["symbol"], "session_date": prior["session_date"], "poc": float(prior["developing_poc"]), "vah": float(prior["vah"]), "val": float(prior["val"]), "h3": float(prior["h3"]), "l3": float(prior["l3"]), "pivot": float(prior["pivot"])}


@router.post("/model-predictions")
def model_predictions(request: AnalyzeRequest) -> dict[str, object]:
    features, _scores, _alerts = build_analysis(request.csv_path, request.symbol)
    predictions: dict[str, object] = {}
    for name in ["day_type_model", "breakout_model", "reversal_model"]:
        try:
            predictions[name] = float(predict_frame(name, features).iloc[-1])
        except FileNotFoundError:
            predictions[name] = None
    predictions["day_type_summary"] = label_day_type(features).tail(1).to_dict(orient="records")
    return predictions
