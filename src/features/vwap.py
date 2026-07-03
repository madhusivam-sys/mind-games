from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class VwapEngine:
    slope_window: int = 5

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        grouped = working.groupby(["symbol", "session_date"], sort=False)
        cumulative_volume = grouped["volume"].cumsum().replace(0.0, pd.NA)
        cumulative_value = (working["typical_price"] * working["volume"]).groupby([working["symbol"], working["session_date"]], sort=False).cumsum()
        working["vwap"] = cumulative_value / cumulative_volume
        working["vwap_slope"] = grouped["vwap"].diff(self.slope_window).fillna(grouped["vwap"].diff()).fillna(0.0)
        working["distance_to_vwap"] = working["close"] - working["vwap"]
        working["vwap_reclaim"] = ((working["close"] > working["vwap"]) & (working["close"].shift(1) <= working["vwap"].shift(1))).fillna(False).astype(int)
        working["acceptance_above_vwap"] = (working["close"] > working["vwap"]).astype(int)
        working["rejection_below_vwap"] = ((working["low"] < working["vwap"]) & (working["close"] > working["vwap"])).astype(int)
        return working
