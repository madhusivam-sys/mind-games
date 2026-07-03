from __future__ import annotations

import pandas as pd


def add_session_columns(frame: pd.DataFrame, default_symbol: str = "NIFTY_FUT") -> pd.DataFrame:
    working = frame.copy()
    if "symbol" not in working.columns:
        working["symbol"] = default_symbol
    working["session_date"] = working["timestamp"].dt.strftime("%Y-%m-%d")
    working["bar_index"] = working.groupby(["symbol", "session_date"]).cumcount()
    working["typical_price"] = working[["high", "low", "close"]].mean(axis=1)
    working["minutes_from_open"] = working.groupby(["symbol", "session_date"])["timestamp"].transform(
        lambda series: (series.dt.hour * 60 + series.dt.minute) - (series.dt.hour.iloc[0] * 60 + series.dt.minute.iloc[0])
    )
    return working
