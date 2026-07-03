from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class CprEngine:
    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        pivot = (working["prev_high"] + working["prev_low"] + working["prev_close"]) / 3.0
        bc = (working["prev_high"] + working["prev_low"]) / 2.0
        tc = pivot + (pivot - bc)
        working["pivot"] = pivot
        working["bc"] = bc
        working["tc"] = tc
        working["cpr_width"] = (tc - bc).abs()
        for level in ["pivot", "bc", "tc"]:
            working[f"distance_to_{level}"] = working["close"] - working[level]
        return working
