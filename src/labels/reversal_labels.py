from __future__ import annotations

import pandas as pd


def _forward_window_extreme(series: pd.Series, horizon: int, fn: str) -> pd.Series:
    shifted = series.shift(-1)
    reversed_shifted = shifted.iloc[::-1]
    rolled = getattr(reversed_shifted.rolling(horizon, min_periods=1), fn)()
    return rolled.iloc[::-1]


def label_reversal_success(feature_frame: pd.DataFrame, horizon: int = 3, threshold: float = 8.0) -> pd.DataFrame:
    grouped = feature_frame.groupby(["symbol", "session_date"], sort=False)
    future_close = grouped["close"].shift(-horizon)
    future_high = grouped["high"].transform(lambda series: _forward_window_extreme(series, horizon, "max"))
    future_low = grouped["low"].transform(lambda series: _forward_window_extreme(series, horizon, "min"))
    mfe = future_high - feature_frame["close"]
    mae = future_low - feature_frame["close"]
    reversal = ((feature_frame["distance_to_val"].abs() <= 10) | (feature_frame["distance_to_vah"].abs() <= 10)).astype(int)
    success = ((reversal == 1) & ((future_close - feature_frame["close"]).abs() > threshold)).astype(int)
    return pd.DataFrame({"reversal_success": success, "mfe": mfe.fillna(0.0), "mae": mae.fillna(0.0)})
