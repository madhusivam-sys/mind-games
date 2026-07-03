from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from features.feature_store import FeatureStoreBuilder
from ingestion.session_builder import add_session_columns
from ingestion.validate_data import validate_intraday_frame
from rules.alert_engine import AlertEngine
from rules.setup_scores import ScoreResult, SetupScoreEngine
from services.market_data_service import MarketDataService, MarketDataSnapshot
from utils.logging import get_logger

logger = get_logger(__name__)

RAW_BAR_COLUMNS = ["timestamp", "symbol", "open", "high", "low", "close", "volume", "delta", "cvd", "bid_volume", "ask_volume"]
ACTIONABLE_LABELS = {"buy", "sell", "alert", "warning", "high"}


@dataclass(slots=True)
class AnalysisBundle:
    """Combined output of feature engineering, scoring, and alerts."""

    feature_frame: pd.DataFrame
    latest_scores: list[ScoreResult]
    alerts: list[dict[str, object]]
    warnings: list[str]
    source_path: Path | str
    watch_scores: list[ScoreResult] = field(default_factory=list)
    confirmed_feature_frame: pd.DataFrame | None = None


class SignalService:
    """Decision-support orchestration built on top of market data snapshots."""

    def __init__(
        self,
        market_data_service: MarketDataService | None = None,
        store: FeatureStoreBuilder | None = None,
        score_engine: SetupScoreEngine | None = None,
        alert_engine: AlertEngine | None = None,
    ) -> None:
        self.market_data_service = market_data_service or MarketDataService()
        self.store = store or FeatureStoreBuilder()
        self.score_engine = score_engine or SetupScoreEngine()
        self.alert_engine = alert_engine or AlertEngine()

    def analyze(self, csv_path: str | Path | None = None, symbol: str | None = None) -> AnalysisBundle:
        snapshot = self.market_data_service.load(csv_path=csv_path, symbol=symbol)
        return self.analyze_snapshot(snapshot, symbol=symbol)

    def analyze_snapshot(self, snapshot: MarketDataSnapshot, symbol: str | None = None) -> AnalysisBundle:
        logger.info("Running signal analysis for source=%s symbol=%s", snapshot.source_path, symbol)
        features = self.store.build(snapshot.frame)
        latest_row = self._latest_row(features, symbol)
        one_minute_scores = self.score_engine.score_row(latest_row)
        watch_scores = [self._as_watch(score) for score in one_minute_scores]

        confirmed_frame = self._build_confirmed_feature_frame(snapshot.frame)
        confirmed_scores = watch_scores
        alert_frame = features
        if confirmed_frame is not None and not confirmed_frame.empty:
            confirmed_row = self._latest_row(confirmed_frame, symbol)
            confirmed_scores = self.score_engine.score_row(confirmed_row)
            alert_frame = confirmed_frame

        features = features.copy()
        failed_breakout = next((item.score for item in confirmed_scores if item.setup_name == "failed_breakout"), 0)
        features["failed_breakout_score"] = failed_breakout
        alerts = [asdict(alert) for alert in self.alert_engine.build(alert_frame.tail(10))]
        return AnalysisBundle(
            feature_frame=features,
            latest_scores=confirmed_scores,
            alerts=alerts,
            warnings=snapshot.warnings,
            source_path=snapshot.source_path,
            watch_scores=watch_scores,
            confirmed_feature_frame=confirmed_frame,
        )

    def _build_confirmed_feature_frame(self, frame: pd.DataFrame) -> pd.DataFrame | None:
        base_columns = [column for column in RAW_BAR_COLUMNS if column in frame.columns]
        required_columns = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
        if required_columns - set(base_columns):
            return None
        working = frame[base_columns].copy()
        if working.empty or len(working) < 5:
            return None

        working["timestamp"] = pd.to_datetime(working["timestamp"])
        working = working.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        working["session_date"] = working["timestamp"].dt.strftime("%Y-%m-%d")

        aggregation_map: dict[str, str] = {
            "timestamp": "last",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        if "delta" in working.columns:
            aggregation_map["delta"] = "sum"
        if "cvd" in working.columns:
            aggregation_map["cvd"] = "last"
        if "bid_volume" in working.columns:
            aggregation_map["bid_volume"] = "sum"
        if "ask_volume" in working.columns:
            aggregation_map["ask_volume"] = "sum"

        confirmed_parts: list[pd.DataFrame] = []
        for (symbol, session_date), session_frame in working.groupby(["symbol", "session_date"], sort=False):
            session_frame = session_frame.reset_index(drop=True)
            session_frame["five_min_group"] = session_frame.index // 5
            aggregated = session_frame.groupby("five_min_group", sort=True).agg(aggregation_map)
            counts = session_frame.groupby("five_min_group", sort=True).size()
            aggregated = aggregated[counts == 5].reset_index(drop=True)
            if aggregated.empty:
                continue
            aggregated["symbol"] = symbol
            aggregated["session_date"] = session_date
            if "delta" not in aggregated.columns:
                aggregated["delta"] = 0.0
            if "cvd" not in aggregated.columns:
                aggregated["cvd"] = aggregated["delta"].cumsum()
            if "bid_volume" not in aggregated.columns:
                aggregated["bid_volume"] = 0.0
            if "ask_volume" not in aggregated.columns:
                aggregated["ask_volume"] = 0.0
            confirmed_parts.append(aggregated)

        if not confirmed_parts:
            return None

        confirmed_frame = pd.concat(confirmed_parts, ignore_index=True)
        validation = validate_intraday_frame(confirmed_frame)
        normalized = add_session_columns(validation.frame)
        numeric_columns = [column for column in normalized.columns if column not in {"timestamp", "symbol", "session_date"}]
        normalized[numeric_columns] = normalized[numeric_columns].apply(pd.to_numeric, errors="coerce")
        return self.store.build(normalized)

    @staticmethod
    def _latest_row(features: pd.DataFrame, symbol: str | None) -> pd.Series:
        if symbol is not None and "symbol" in features.columns:
            matched = features[features["symbol"] == symbol]
            if not matched.empty:
                return matched.iloc[-1]
        return features.iloc[-1]

    @staticmethod
    def _as_watch(score: ScoreResult) -> ScoreResult:
        if score.label in ACTIONABLE_LABELS:
            return ScoreResult(
                timestamp=score.timestamp,
                symbol=score.symbol,
                setup_name=score.setup_name,
                score=score.score,
                label="watch",
                reasons=score.reasons,
                invalidation=score.invalidation,
                summary=f"{score.summary} Pending 5-minute candle close confirmation.",
            )
        return score


def to_jsonifiable(record: dict[str, Any]) -> dict[str, Any]:
    """Convert pandas and datetime-like objects into JSON-safe values."""

    result: dict[str, Any] = {}
    for key, value in record.items():
        result[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return result
