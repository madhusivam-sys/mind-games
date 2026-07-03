from __future__ import annotations

import numpy as np
import pandas as pd


def safe_divide(numerator: pd.Series | np.ndarray, denominator: pd.Series | np.ndarray) -> pd.Series:
    numerator_series = pd.Series(numerator)
    denominator_series = pd.Series(denominator).replace(0.0, np.nan)
    return numerator_series / denominator_series


def clip_score(score: float) -> int:
    return int(max(0.0, min(100.0, round(score))))
