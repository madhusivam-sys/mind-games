from __future__ import annotations

import pandas as pd


def label_day_type(feature_frame: pd.DataFrame) -> pd.DataFrame:
    summary = feature_frame.groupby(["symbol", "session_date"], sort=False).agg(
        session_range=("session_range", "max"),
        close_change=("close", lambda series: series.iloc[-1] - series.iloc[0]),
        poc_shift=("poc_migration", "sum"),
    ).reset_index()
    summary["day_type"] = "balanced"
    summary.loc[(summary["close_change"].abs() > summary["session_range"] * 0.35), "day_type"] = "trend"
    summary.loc[(summary["poc_shift"].abs() > 8) & (summary["day_type"] != "trend"), "day_type"] = "double_distribution"
    summary.loc[(summary["session_range"] < summary["session_range"].median()), "day_type"] = summary.loc[(summary["session_range"] < summary["session_range"].median()), "day_type"].replace({"balanced": "neutral"})
    return summary[["symbol", "session_date", "day_type"]]
