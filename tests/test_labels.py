from __future__ import annotations

import pandas as pd

from features.feature_store import load_sample_features
from labels.breakout_labels import label_breakout_success
from labels.day_type import label_day_type
from labels.reversal_labels import label_reversal_success


def test_day_type_labels_include_session_rows() -> None:
    frame = load_sample_features()
    labels = label_day_type(frame)
    assert len(labels) == frame["session_date"].nunique()


def test_breakout_and_reversal_labels_align_to_feature_frame() -> None:
    frame = load_sample_features()
    breakout = label_breakout_success(frame)
    reversal = label_reversal_success(frame)
    assert len(breakout) == len(frame)
    assert len(reversal) == len(frame)
    assert {"reversal_success", "mfe", "mae"}.issubset(reversal.columns)


def test_reversal_excursion_uses_future_window() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["NIFTY_FUT"] * 4,
            "session_date": ["2026-03-14"] * 4,
            "close": [100.0, 101.0, 102.0, 103.0],
            "high": [100.0, 110.0, 105.0, 104.0],
            "low": [99.0, 98.0, 97.0, 96.0],
            "distance_to_val": [0.0, 0.0, 0.0, 0.0],
            "distance_to_vah": [20.0, 20.0, 20.0, 20.0],
        }
    )
    labeled = label_reversal_success(frame, horizon=2, threshold=1.0)
    assert labeled.loc[0, "mfe"] == 10.0
    assert labeled.loc[0, "mae"] == -3.0
