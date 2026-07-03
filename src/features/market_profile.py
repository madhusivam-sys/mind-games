from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _profile_levels(window: pd.DataFrame) -> tuple[float, float, float]:
    grouped = window.groupby(window["close"].round(2))["volume"].sum().sort_index()
    cumulative = grouped.cumsum()
    total = grouped.sum()
    poc = float(grouped.idxmax())
    vah = float(grouped.index[min(np.searchsorted(cumulative.to_numpy(), total * 0.85, side="left"), len(grouped.index) - 1)])
    val = float(grouped.index[min(np.searchsorted(cumulative.to_numpy(), total * 0.15, side="left"), len(grouped.index) - 1)])
    return poc, vah, val


@dataclass(slots=True)
class MarketProfileEngine:
    ib_bars: int = 12
    poor_extreme_tolerance: float = 0.1

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        sessions: list[pd.DataFrame] = []
        for _, session in frame.groupby(["symbol", "session_date"], sort=False):
            session = session.copy()
            session["session_high"] = session["high"].cummax()
            session["session_low"] = session["low"].cummin()
            session["session_range"] = session["session_high"] - session["session_low"]
            session["ib_high"] = session["high"].cummax()
            session["ib_low"] = session["low"].cummin()
            if len(session) > self.ib_bars:
                session.loc[session.index[self.ib_bars :], "ib_high"] = session["ib_high"].iloc[self.ib_bars - 1]
                session.loc[session.index[self.ib_bars :], "ib_low"] = session["ib_low"].iloc[self.ib_bars - 1]
            session["ib_range"] = session["ib_high"] - session["ib_low"]

            poc: list[float] = []
            vah: list[float] = []
            val: list[float] = []
            for index in range(len(session)):
                current = session.iloc[: index + 1]
                p, h, l = _profile_levels(current)
                poc.append(p)
                vah.append(h)
                val.append(l)
            session["developing_poc"] = poc
            session["vah"] = vah
            session["val"] = val
            session["poc_migration"] = session["developing_poc"].diff().fillna(0.0)
            session["distance_to_poc"] = session["close"] - session["developing_poc"]
            session["distance_to_vah"] = session["close"] - session["vah"]
            session["distance_to_val"] = session["close"] - session["val"]

            tolerance = session["close"].diff().abs().expanding().median().fillna(self.poor_extreme_tolerance).clip(lower=self.poor_extreme_tolerance)
            rounded_high = session["high"].round(2)
            rounded_low = session["low"].round(2)
            seen_high_hits = rounded_high.groupby(rounded_high, sort=False).cumcount() + 1
            seen_low_hits = rounded_low.groupby(rounded_low, sort=False).cumcount() + 1
            session["poor_high"] = ((session["high"] >= session["session_high"] - tolerance) & (seen_high_hits >= 2)).astype(int)
            session["poor_low"] = ((session["low"] <= session["session_low"] + tolerance) & (seen_low_hits >= 2)).astype(int)
            session["excess_high"] = ((session["high"] == session["session_high"]) & (session["close"] < session["high"] - tolerance)).astype(int)
            session["excess_low"] = ((session["low"] == session["session_low"]) & (session["close"] > session["low"] + tolerance)).astype(int)
            sessions.append(session)

        result = pd.concat(sessions, ignore_index=True)
        summary = (
            result.groupby(["symbol", "session_date"], sort=False)
            .agg(prior_poc=("developing_poc", "last"), prior_vah=("vah", "last"), prior_val=("val", "last"))
            .groupby(level=0)
            .shift(1)
            .reset_index()
        )
        result = result.merge(summary, on=["symbol", "session_date"], how="left")
        result["value_shift"] = result["developing_poc"] - result["prior_poc"]
        result["acceptance_above_prior_value"] = (result["close"] > result["prior_vah"]).astype(int)
        result["acceptance_below_prior_value"] = (result["close"] < result["prior_val"]).astype(int)
        session_open = result.groupby(["symbol", "session_date"], sort=False)["open"].transform("first")
        result["open_location_vs_prior_value"] = np.select([session_open > result["prior_vah"], session_open < result["prior_val"]], [1, -1], default=0)
        return result
