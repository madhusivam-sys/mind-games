from __future__ import annotations

import pandas as pd


def summarize_setups(signal_frame: pd.DataFrame) -> pd.DataFrame:
    return signal_frame.groupby("setup_name", sort=False).agg(avg_score=("score", "mean"), count=("score", "size")).reset_index().sort_values("avg_score", ascending=False)
