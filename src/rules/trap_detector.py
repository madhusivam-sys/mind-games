from __future__ import annotations

import pandas as pd


def trap_flags(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame[["timestamp", "symbol"]].copy()
    result["buyer_trap"] = ((frame["trapped_buyer_proxy"] == 1) | ((frame["price_cvd_divergence"] == 1) & (frame["close"] < frame["open"]))).astype(int)
    result["seller_trap"] = ((frame["trapped_seller_proxy"] == 1) | ((frame["price_cvd_divergence"] == 1) & (frame["close"] > frame["open"]))).astype(int)
    return result
