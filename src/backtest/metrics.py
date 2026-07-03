from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class BacktestMetrics:
    hit_rate: float
    expectancy: float
    average_excursion: float
    max_drawdown: float


def compute_metrics(results: pd.DataFrame) -> BacktestMetrics:
    pnl = results["pnl"]
    hit_rate = float((pnl > 0).mean()) if not pnl.empty else 0.0
    expectancy = float(pnl.mean()) if not pnl.empty else 0.0
    average_excursion = float(results["excursion"].mean()) if "excursion" in results else 0.0
    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()
    return BacktestMetrics(hit_rate, expectancy, average_excursion, float(drawdown.min() if not drawdown.empty else 0.0))
