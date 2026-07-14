from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


class _FenwickTree:
    """Maintain prefix volume totals with logarithmic updates and percentile lookup."""

    def __init__(self, size: int) -> None:
        self.values = [0.0] * (size + 1)

    def add(self, index: int, value: float) -> None:
        position = index + 1
        while position < len(self.values):
            self.values[position] += value
            position += position & -position

    def lower_bound(self, target: float) -> int:
        if target <= 0:
            return 0
        index = 0
        accumulated = 0.0
        bit = 1 << (len(self.values).bit_length() - 1)
        while bit:
            candidate = index + bit
            if candidate < len(self.values) and accumulated + self.values[candidate] < target:
                index = candidate
                accumulated += self.values[candidate]
            bit >>= 1
        return min(index, len(self.values) - 2)


def _developing_profile_levels(close: pd.Series, volume: pd.Series) -> tuple[list[float], list[float], list[float]]:
    """Build prefix-stable profile levels with an incremental price-volume accumulator."""

    rounded_close = close.round(2)
    ordered_prices = sorted(float(value) for value in rounded_close.unique())
    price_indexes = {price: index for index, price in enumerate(ordered_prices)}
    volume_by_price = [0.0] * len(ordered_prices)
    volume_tree = _FenwickTree(len(ordered_prices))
    pocs: list[float] = []
    vahs: list[float] = []
    vals: list[float] = []
    total = 0.0
    poc = ordered_prices[0]
    poc_volume = float("-inf")
    for price_value, volume_value in zip(rounded_close, volume.fillna(0.0), strict=True):
        price = float(price_value)
        traded_volume = float(volume_value)
        price_index = price_indexes[price]
        volume_by_price[price_index] += traded_volume
        volume_tree.add(price_index, traded_volume)
        total += traded_volume

        updated_volume = volume_by_price[price_index]
        if updated_volume > poc_volume or (updated_volume == poc_volume and price < poc):
            poc = price
            poc_volume = updated_volume
        value_high_index = volume_tree.lower_bound(total * 0.85)
        value_low_index = volume_tree.lower_bound(total * 0.15)
        pocs.append(float(poc))
        vahs.append(float(ordered_prices[value_high_index]))
        vals.append(float(ordered_prices[value_low_index]))
    return pocs, vahs, vals


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

            poc, vah, val = _developing_profile_levels(session["close"], session["volume"])
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
