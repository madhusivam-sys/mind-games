from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class VolumeProfileEngine:
    """Approximate high-volume and low-volume nodes using close-price aggregation."""

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        sessions: list[pd.DataFrame] = []
        for _, session in frame.groupby(["symbol", "session_date"], sort=False):
            session = session.copy()
            hvn: list[float] = []
            lvn: list[float] = []
            shape: list[str] = []
            for index in range(len(session)):
                current = session.iloc[: index + 1]
                grouped = current.groupby(current["close"].round(2))["volume"].sum().sort_values()
                lvn.append(float(grouped.index[0]))
                hvn.append(float(grouped.index[-1]))
                shape.append("b_shape" if grouped.std() > grouped.mean() else "balanced")
            session["hvn"] = hvn
            session["lvn"] = lvn
            session["distance_to_hvn"] = session["close"] - session["hvn"]
            session["distance_to_lvn"] = session["close"] - session["lvn"]
            session["breakout_through_lvn"] = ((session["close"] > session["lvn"]) & (session["close"].shift(1) <= session["lvn"].shift(1))).fillna(False).astype(int)
            session["rejection_from_hvn"] = ((session["high"] >= session["hvn"]) & (session["close"] < session["hvn"])).astype(int)
            session["distribution_shape"] = shape
            sessions.append(session)
        return pd.concat(sessions, ignore_index=True)
