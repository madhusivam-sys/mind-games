from __future__ import annotations

import pandas as pd


def ensure_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="raise")


def minutes_from_open(timestamp_series: pd.Series) -> pd.Series:
    open_minutes = timestamp_series.dt.hour * 60 + timestamp_series.dt.minute
    return open_minutes - open_minutes.groupby(timestamp_series.dt.date).transform("min")
