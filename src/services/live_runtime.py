from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from integrations.live_market_data_client import LiveMarketDataClientError, TrueDataLiveClient
from integrations.market_data_client import MarketDataClientError
from models.predict import predict_frame
from services.briefing import build_trade_brief
from services.live_signal_service import LiveSignalService
from services.market_data_service import MarketDataService, build_live_market_data_service
from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class LiveRuntimeStatus:
    running: bool
    source: str
    completed_bars: int
    has_analysis: bool


class LiveRuntime:
    """Manage the optional TrueData live stream lifecycle for the API layer."""

    def __init__(
        self,
        live_service: LiveSignalService | None = None,
        live_client: TrueDataLiveClient | None = None,
        market_data_service: MarketDataService | None = None,
    ) -> None:
        self.live_service = live_service or LiveSignalService()
        self.live_client = live_client or TrueDataLiveClient(callbacks=self.live_service.build_callbacks())
        self.market_data_service = market_data_service or build_live_market_data_service()
        self._running = False

    def start(self, symbols: list[str] | None = None) -> LiveRuntimeStatus:
        if not self._running:
            self._seed_backfill(symbols=symbols or [get_settings().default_symbol])
            self.live_client.callbacks = self.live_service.build_callbacks()
            self.live_client.start()
            self._running = True
            logger.info("Live runtime started")
        return self.status()

    def stop(self) -> LiveRuntimeStatus:
        if self._running:
            self.live_client.stop()
            self._running = False
            logger.info("Live runtime stopped")
        return self.status()

    def status(self) -> LiveRuntimeStatus:
        return LiveRuntimeStatus(
            running=self._running,
            source=self.live_service.source_name,
            completed_bars=self.live_service.aggregator.completed_bars,
            has_analysis=self.live_service.latest_analysis is not None,
        )

    def latest_signals(self) -> dict[str, Any]:
        analysis = self.live_service.latest_analysis
        if analysis is None:
            raise LiveMarketDataClientError("Live analysis is not available yet. Start the live runtime and wait for a completed bar.")
        latest_bar = analysis.feature_frame.iloc[-1].to_dict()
        signal_snapshot = {
            "scores": [asdict(result) for result in analysis.latest_scores],
            "watch_scores_1m": [asdict(result) for result in analysis.watch_scores],
            "alerts": analysis.alerts,
            "latest_bar": latest_bar,
        }
        prior_summary = self._prior_session_summary(analysis.feature_frame)
        return {
            "source": str(analysis.source_path),
            "data_source": "truedata-live",
            "session_mode": "live",
            "warnings": analysis.warnings,
            "as_of_timestamp": analysis.feature_frame.iloc[-1]["timestamp"].isoformat(),
            "scores": signal_snapshot["scores"],
            "watch_scores_1m": signal_snapshot["watch_scores_1m"],
            "alerts": signal_snapshot["alerts"],
            "briefing": build_trade_brief(signal_snapshot, prior_summary).to_dict(),
            "model_predictions": self._latest_model_predictions(analysis.feature_frame),
            "latest_bar": latest_bar,
            "bars": analysis.feature_frame.tail(120).to_dict(orient="records"),
        }

    def latest_snapshot(self, include_open_bar: bool = True) -> dict[str, Any]:
        snapshot = self.live_service.latest_snapshot(include_open_bar=include_open_bar)
        if snapshot.frame.empty:
            raise LiveMarketDataClientError("Live snapshot is not available yet. No bars have been formed.")
        return {
            "source": str(snapshot.source_path),
            "warnings": snapshot.warnings,
            "rows": len(snapshot.frame),
            "data": snapshot.frame.to_dict(orient="records"),
        }

    def _seed_backfill(self, symbols: list[str]) -> None:
        settings = get_settings()
        for symbol in symbols:
            try:
                snapshot = self.market_data_service.history(symbol=symbol, interval=settings.truedata_live_backfill_interval, limit=settings.truedata_live_backfill_bars)
            except MarketDataClientError as exc:
                logger.warning("Unable to seed live backfill for symbol=%s error=%s", symbol, exc)
                continue
            self.live_service.seed_history(snapshot.frame)

    @staticmethod
    def _latest_model_predictions(feature_frame) -> dict[str, object]:
        predictions: dict[str, object] = {}
        for name in ["day_type_model", "breakout_model", "reversal_model"]:
            try:
                predictions[name] = float(predict_frame(name, feature_frame).iloc[-1])
            except FileNotFoundError:
                predictions[name] = None
        return predictions

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _prior_session_summary(cls, feature_frame) -> dict[str, object]:
        previous_session = feature_frame["session_date"].unique()[-2] if feature_frame["session_date"].nunique() > 1 else feature_frame["session_date"].iloc[-1]
        prior = feature_frame[feature_frame["session_date"] == previous_session].iloc[-1]
        close = cls._safe_float(prior.get("close"), 0.0)
        return {
            "symbol": str(prior.get("symbol", "")),
            "session_date": str(prior.get("session_date", "")),
            "poc": cls._safe_float(prior.get("developing_poc"), close),
            "vah": cls._safe_float(prior.get("vah"), close),
            "val": cls._safe_float(prior.get("val"), close),
            "h3": cls._safe_float(prior.get("h3"), 0.0),
            "h4": cls._safe_float(prior.get("h4"), 0.0),
            "l3": cls._safe_float(prior.get("l3"), 0.0),
            "l4": cls._safe_float(prior.get("l4"), 0.0),
            "pivot": cls._safe_float(prior.get("pivot"), 0.0),
        }

