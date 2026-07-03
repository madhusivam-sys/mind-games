from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
OPTIONAL_COLUMNS = ["symbol", "delta", "cvd", "bid_volume", "ask_volume", "oi", "oi_change", "trade_count"]


@dataclass(slots=True)
class ValidationResult:
    frame: pd.DataFrame
    warnings: list[str]


def validate_intraday_frame(frame: pd.DataFrame) -> ValidationResult:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    warnings: list[str] = []
    working = frame.copy()
    for column in OPTIONAL_COLUMNS:
        if column not in working.columns:
            working[column] = pd.NA

    null_rows = int(working[REQUIRED_COLUMNS].isna().any(axis=1).sum())
    if null_rows:
        warnings.append(f"Dropped {null_rows} rows with missing required fields.")
    working = working.dropna(subset=REQUIRED_COLUMNS).reset_index(drop=True)
    return ValidationResult(frame=working, warnings=warnings)
