from __future__ import annotations

import pandas as pd

from backtest.metrics import BacktestMetrics, compute_metrics
from backtest.scenarios import ScenarioConfig


def run_backtest(feature_frame: pd.DataFrame, signal_column: str, scenario: ScenarioConfig | None = None) -> tuple[pd.DataFrame, BacktestMetrics]:
    active = scenario or ScenarioConfig()
    results = feature_frame[["timestamp", "symbol", "close"]].copy()
    future_move = feature_frame.groupby(["symbol", "session_date"], sort=False)["close"].shift(-3) - feature_frame["close"]
    results["signal"] = feature_frame[signal_column]
    results["pnl"] = future_move.fillna(0.0) * results["signal"] / max(active.stop_multiple, 1.0)
    results["excursion"] = future_move.abs().fillna(0.0)
    return results, compute_metrics(results)
