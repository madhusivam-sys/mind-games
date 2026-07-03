from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class SessionContextEngine:
    atr_window: int = 14

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        grouped = working.groupby("symbol", sort=False)
        true_range = pd.concat([
            (working["high"] - working["low"]),
            (working["high"] - grouped["close"].shift(1)).abs(),
            (working["low"] - grouped["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        working["atr_regime"] = true_range.rolling(self.atr_window, min_periods=1).mean()

        session_summary = (
            working.groupby(["symbol", "session_date"], sort=False)
            .agg(session_open=("open", "first"), prev_session_close=("close", "last"))
            .groupby(level=0)
            .shift(1)
            .reset_index()
        )
        working = working.merge(session_summary, on=["symbol", "session_date"], how="left")
        working["gap_context"] = np.select([working["session_open"] > working["prev_session_close"], working["session_open"] < working["prev_session_close"]], [1, -1], default=0)
        working["opening_type"] = "placeholder"
        working["time_bucket"] = pd.cut(working["minutes_from_open"], bins=[-1, 30, 90, 180, 10000], labels=["open", "early", "mid", "late"])
        return working
