from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class CamarillaEngine:
    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        prior = (
            working.groupby(["symbol", "session_date"], sort=False)
            .agg(prev_high=("high", "max"), prev_low=("low", "min"), prev_close=("close", "last"))
            .groupby(level=0)
            .shift(1)
            .reset_index()
        )
        working = working.merge(prior, on=["symbol", "session_date"], how="left")
        price_range = working["prev_high"] - working["prev_low"]
        working["h3"] = working["prev_close"] + (price_range * 1.1 / 4.0)
        working["h4"] = working["prev_close"] + (price_range * 1.1 / 2.0)
        working["l3"] = working["prev_close"] - (price_range * 1.1 / 4.0)
        working["l4"] = working["prev_close"] - (price_range * 1.1 / 2.0)
        working["h5"] = (working["prev_high"] / working["prev_low"].replace(0.0, np.nan)) * working["prev_close"]
        working["l5"] = working["prev_close"] - (working["h5"] - working["prev_close"])
        for level in ["h3", "h4", "h5", "l3", "l4", "l5"]:
            working[f"distance_to_{level}"] = working["close"] - working[level]
            working[f"reaction_near_{level}"] = (working[f"distance_to_{level}"].abs() <= 10).astype(int)
        return working
