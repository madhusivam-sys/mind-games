from __future__ import annotations

import pandas as pd


def label_breakout_success(feature_frame: pd.DataFrame, horizon: int = 3, threshold: float = 8.0) -> pd.Series:
    future_move = feature_frame.groupby(["symbol", "session_date"], sort=False)["close"].shift(-horizon) - feature_frame["close"]
    breakout_reference = (feature_frame["close"] > feature_frame[["vah", "h4"]].min(axis=1)).astype(int)
    return ((breakout_reference == 1) & (future_move > threshold)).astype(int).rename("breakout_success")
