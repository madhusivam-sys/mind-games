from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ingestion.session_builder import add_session_columns
from ingestion.validate_data import validate_intraday_frame
from utils.time import ensure_timestamp


@dataclass(slots=True)
class CsvDataLoader:
    """Load CSV intraday data into a clean, session-aware dataframe."""

    default_symbol: str = "NIFTY_FUT"

    def load(self, csv_path: str | Path) -> tuple[pd.DataFrame, list[str]]:
        frame = pd.read_csv(csv_path)
        frame["timestamp"] = ensure_timestamp(frame["timestamp"])
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        validation = validate_intraday_frame(frame)
        clean = add_session_columns(validation.frame, default_symbol=self.default_symbol)
        numeric_columns = [column for column in clean.columns if column != "timestamp" and column != "symbol" and column != "session_date"]
        clean[numeric_columns] = clean[numeric_columns].apply(pd.to_numeric, errors="coerce")
        return clean.reset_index(drop=True), validation.warnings
