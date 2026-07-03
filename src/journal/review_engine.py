from __future__ import annotations

import pandas as pd


def build_review_table(feature_frame: pd.DataFrame) -> pd.DataFrame:
    review = feature_frame[["timestamp", "symbol", "close", "vah", "val", "developing_poc", "vwap"]].copy()
    review["note"] = "TODO: add discretionary trade notes and replay metadata."
    return review
