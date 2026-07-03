from __future__ import annotations

import pandas as pd


def confluence_view(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame[["timestamp", "symbol", "close"]].copy()
    result["structure_confluence"] = (
        (frame["distance_to_poc"].abs() <= 8).astype(int)
        + (frame["distance_to_vwap"].abs() <= 8).astype(int)
        + ((frame["distance_to_h3"].abs() <= 8) | (frame["distance_to_l3"].abs() <= 8)).astype(int)
        + (frame["distance_to_pivot"].abs() <= 8).astype(int)
    )
    result["flow_confluence"] = ((frame["aggression_score"] >= 60).astype(int) + (frame["absorption_proxy"] == 1).astype(int) + (frame["imbalance_cluster_count"] >= 2).astype(int))
    result["confluence_score"] = ((result["structure_confluence"] + result["flow_confluence"]) / 7.0 * 100).round(0)
    return result
